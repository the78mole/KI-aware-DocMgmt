import hashlib
import mimetypes
import tempfile
import uuid
from datetime import datetime
from pathlib import PurePath
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from docmgmt.db import get_session
from docmgmt.models import Conversion, ConversionStatus, Document
from docmgmt.storage import CHUNK_SIZE, ObjectNotFoundError, ObjectStorage, get_storage

router = APIRouter(prefix="/api/documents", tags=["documents"])

SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[ObjectStorage, Depends(get_storage)]

ALLOWED_CONTENT_TYPES = {"application/pdf"}


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    filename: str
    content_type: str
    size: int
    sha256: str
    conversion_status: ConversionStatus | None
    created_at: datetime


class ConversionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ConversionStatus
    converter: str | None
    assets: list[str]
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


def _get_or_404(session: Session, document_id: uuid.UUID) -> Document:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dokument nicht gefunden")
    return document


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DocumentOut)
def upload_document(
    session: SessionDep,
    storage: StorageDep,
    file: Annotated[UploadFile, File(description="PDF-Datei, z. B. ein Datenblatt")],
    title: Annotated[str | None, Form()] = None,
) -> Document:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Nur PDF-Dateien werden angenommen")

    filename = PurePath(file.filename or "dokument.pdf").name
    digest = hashlib.sha256()
    size = 0
    with tempfile.SpooledTemporaryFile(max_size=16 * CHUNK_SIZE) as buffer:
        while chunk := file.file.read(CHUNK_SIZE):
            digest.update(chunk)
            size += len(chunk)
            buffer.write(chunk)
        if size == 0:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Die Datei ist leer")

        sha256 = digest.hexdigest()
        existing = session.scalar(select(Document).where(Document.sha256 == sha256))
        if existing is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                {"message": "Dieses Dokument ist bereits eingecheckt", "document_id": str(existing.id)},
            )

        document_id = uuid.uuid4()
        s3_key = f"documents/{document_id}/original.pdf"
        buffer.seek(0)
        storage.put(s3_key, buffer, file.content_type)

    document = Document(
        id=document_id,
        title=(title or "").strip() or PurePath(filename).stem,
        filename=filename,
        content_type=file.content_type,
        size=size,
        sha256=sha256,
        s3_key=s3_key,
        conversions=[Conversion()],
    )
    session.add(document)
    session.commit()
    return document


@router.get("", response_model=list[DocumentOut])
def list_documents(session: SessionDep) -> list[Document]:
    return list(session.scalars(select(Document).order_by(Document.created_at.desc())))


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(session: SessionDep, document_id: uuid.UUID) -> Document:
    return _get_or_404(session, document_id)


def _stream(storage: ObjectStorage, key: str, media_type: str, headers: dict[str, str] | None = None):
    try:
        body = storage.open(key)
    except ObjectNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Datei fehlt im Speicher") from exc
    return StreamingResponse(body, media_type=media_type, headers=headers)


@router.get("/{document_id}/file")
def download_document(session: SessionDep, storage: StorageDep, document_id: uuid.UUID) -> StreamingResponse:
    document = _get_or_404(session, document_id)
    return _stream(
        storage,
        document.s3_key,
        document.content_type,
        # RFC 5987, damit auch Umlaute und Sonderzeichen im Dateinamen ankommen
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(document.filename)}"},
    )


@router.get("/{document_id}/markdown", response_class=PlainTextResponse)
def get_markdown(session: SessionDep, document_id: uuid.UUID) -> PlainTextResponse:
    """Markdown der neuesten erfolgreichen Konvertierung. Bilder liegen unter …/conversions/{id}/assets/."""
    document = _get_or_404(session, document_id)
    done = next((c for c in document.conversions if c.status == ConversionStatus.DONE), None)
    if done is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Noch keine fertige Konvertierung")
    return PlainTextResponse(
        done.markdown or "", media_type="text/markdown; charset=utf-8", headers={"X-Conversion-Id": str(done.id)}
    )


@router.get("/{document_id}/conversions", response_model=list[ConversionOut])
def list_conversions(session: SessionDep, document_id: uuid.UUID) -> list[Conversion]:
    return _get_or_404(session, document_id).conversions


@router.post("/{document_id}/conversions", status_code=status.HTTP_202_ACCEPTED, response_model=ConversionOut)
def request_conversion(session: SessionDep, document_id: uuid.UUID) -> Conversion:
    """Stößt eine neue Konvertierung an, z. B. nach einem Fehler oder mit neuerer marker-Version."""
    document = _get_or_404(session, document_id)
    if any(c.status in (ConversionStatus.PENDING, ConversionStatus.PROCESSING) for c in document.conversions):
        raise HTTPException(status.HTTP_409_CONFLICT, "Eine Konvertierung läuft bereits")
    conversion = Conversion(document=document)
    session.add(conversion)
    session.commit()
    return conversion


@router.get("/{document_id}/conversions/{conversion_id}/assets/{name}")
def get_asset(session: SessionDep, storage: StorageDep, document_id: uuid.UUID, conversion_id: uuid.UUID, name: str):
    conversion = session.get(Conversion, conversion_id)
    if conversion is None or conversion.document_id != document_id or name not in conversion.assets:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bild nicht gefunden")
    return _stream(storage, conversion.asset_key(name), mimetypes.guess_type(name)[0] or "application/octet-stream")
