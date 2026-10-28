import hashlib
import tempfile
import uuid
from datetime import datetime
from pathlib import PurePath
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from docmgmt.db import get_session
from docmgmt.models import Document, MarkdownStatus
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
    markdown_status: MarkdownStatus
    created_at: datetime


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


@router.get("/{document_id}/file")
def download_document(session: SessionDep, storage: StorageDep, document_id: uuid.UUID) -> StreamingResponse:
    document = _get_or_404(session, document_id)
    try:
        body = storage.open(document.s3_key)
    except ObjectNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Datei fehlt im Speicher") from exc
    return StreamingResponse(
        body,
        media_type=document.content_type,
        # RFC 5987, damit auch Umlaute und Sonderzeichen im Dateinamen ankommen
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(document.filename)}"},
    )
