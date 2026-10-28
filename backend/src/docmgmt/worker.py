"""Hintergrundjob: wandelt offene Konvertierungen mit marker in Markdown um.

Postgres dient als Warteschlange (`FOR UPDATE SKIP LOCKED`), damit mehrere Worker parallel laufen können.
"""

import io
import logging
import mimetypes
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, create_engine, select, update
from sqlalchemy.orm import Session

from docmgmt.config import Settings, get_settings
from docmgmt.converter import Converter, MarkerServerConverter
from docmgmt.models import Conversion, ConversionStatus
from docmgmt.storage import ObjectStorage, S3Storage

log = logging.getLogger(__name__)

MAX_ERROR_LENGTH = 4000


def claim_next(session: Session) -> Conversion | None:
    conversion = session.scalar(
        select(Conversion)
        .where(Conversion.status == ConversionStatus.PENDING)
        .order_by(Conversion.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if conversion is None:
        return None
    conversion.status = ConversionStatus.PROCESSING
    conversion.started_at = datetime.now(UTC)
    session.commit()
    return conversion


def process(session: Session, conversion: Conversion, storage: ObjectStorage, converter: Converter) -> None:
    document = conversion.document
    conversion.converter = converter.name
    try:
        pdf = b"".join(storage.open(document.s3_key))
        result = converter.convert(pdf, f"{document.id}.pdf")
        for name, data in result.images.items():
            content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
            storage.put(conversion.asset_key(name), io.BytesIO(data), content_type)
    except Exception as exc:
        log.exception("Konvertierung %s für Dokument %s fehlgeschlagen", conversion.id, document.id)
        conversion.status = ConversionStatus.FAILED
        conversion.error = str(exc)[:MAX_ERROR_LENGTH] or type(exc).__name__
    else:
        conversion.status = ConversionStatus.DONE
        conversion.markdown = result.markdown
        conversion.meta = result.meta
        conversion.assets = sorted(result.images)
        log.info("Dokument %s konvertiert (%d Bilder)", document.id, len(result.images))
    conversion.finished_at = datetime.now(UTC)
    session.commit()


def requeue_stale(session: Session, older_than: timedelta) -> int:
    """Setzt Läufe zurück, deren Worker abgestürzt ist, damit sie nicht ewig in `processing` hängen."""
    result = session.execute(
        update(Conversion)
        .where(Conversion.status == ConversionStatus.PROCESSING)
        .where(Conversion.started_at < datetime.now(UTC) - older_than)
        .values(status=ConversionStatus.PENDING, started_at=None)
    )
    session.commit()
    return result.rowcount


def run_once(engine: Engine, storage: ObjectStorage, converter: Converter) -> bool:
    with Session(engine) as session:
        conversion = claim_next(session)
        if conversion is None:
            return False
        process(session, conversion, storage, converter)
        return True


def run_forever(settings: Settings) -> None:  # pragma: no cover - Endlosschleife, Teile sind einzeln getestet
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    storage = S3Storage.from_settings(settings)
    converter = MarkerServerConverter(settings.marker_url, settings.marker_label, mode=settings.marker_mode or None)
    stale_after = timedelta(seconds=settings.conversion_timeout_seconds)
    log.info("Worker gestartet, marker unter %s", settings.marker_url)
    while True:
        with Session(engine) as session:
            if requeued := requeue_stale(session, stale_after):
                log.warning("%d hängende Konvertierungen neu eingereiht", requeued)
        if not run_once(engine, storage, converter):
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_forever(get_settings())
