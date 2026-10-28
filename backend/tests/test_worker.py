from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from docmgmt.converter import ConversionError, ConversionResult
from docmgmt.models import Conversion, ConversionStatus
from docmgmt.worker import claim_next, requeue_stale, run_once
from tests.fakes import FakeConverter, InMemoryStorage
from tests.test_documents import PDF, upload


def only_conversion(engine: Engine) -> Conversion:
    with Session(engine, expire_on_commit=False) as session:
        return session.scalars(select(Conversion)).one()


def test_run_once_without_work_returns_false(client: TestClient, engine: Engine, storage: InMemoryStorage) -> None:
    assert run_once(engine, storage, FakeConverter()) is False


def test_successful_conversion_stores_markdown_meta_and_images(
    client: TestClient, engine: Engine, storage: InMemoryStorage
) -> None:
    document = upload(client).json()
    result = ConversionResult(markdown="# LM317", meta={"page_stats": [1]}, images={"a.png": b"png"})
    converter = FakeConverter(result)

    assert run_once(engine, storage, converter) is True

    conversion = only_conversion(engine)
    assert converter.calls == [(PDF, f"{document['id']}.pdf")]
    assert conversion.status == ConversionStatus.DONE
    assert conversion.converter == "fake-marker 1.0"
    assert conversion.markdown == "# LM317"
    assert conversion.meta == {"page_stats": [1]}
    assert conversion.assets == ["a.png"]
    assert conversion.started_at is not None and conversion.finished_at is not None
    assert storage.objects[f"documents/{document['id']}/conversions/{conversion.id}/a.png"] == (b"png", "image/png")


def test_failed_conversion_records_error(client: TestClient, engine: Engine, storage: InMemoryStorage) -> None:
    upload(client)

    run_once(engine, storage, FakeConverter(error=ConversionError("marker meldet: kaputt")))

    conversion = only_conversion(engine)
    assert conversion.status == ConversionStatus.FAILED
    assert conversion.error == "marker meldet: kaputt"
    assert conversion.markdown is None


def test_missing_pdf_fails_conversion(client: TestClient, engine: Engine, storage: InMemoryStorage) -> None:
    upload(client)
    storage.objects.clear()

    run_once(engine, storage, FakeConverter())

    assert only_conversion(engine).status == ConversionStatus.FAILED


def test_claim_marks_processing(client: TestClient, engine: Engine) -> None:
    upload(client)

    with Session(engine) as session:
        claimed = claim_next(session)
        assert claimed is not None and claimed.status == ConversionStatus.PROCESSING
        assert claim_next(session) is None


def test_requeue_stale_resets_only_old_processing(client: TestClient, engine: Engine) -> None:
    upload(client, content=PDF + b"alt")
    upload(client, content=PDF + b"frisch")
    with Session(engine) as session:
        old, fresh = session.scalars(select(Conversion).order_by(Conversion.created_at)).all()
        old.status = fresh.status = ConversionStatus.PROCESSING
        old.started_at = datetime.now(UTC) - timedelta(hours=2)
        fresh.started_at = datetime.now(UTC)
        session.commit()

        assert requeue_stale(session, timedelta(hours=1)) == 1
        session.refresh(old)
        session.refresh(fresh)
        assert old.status == ConversionStatus.PENDING and old.started_at is None
        assert fresh.status == ConversionStatus.PROCESSING
