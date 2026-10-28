import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from docmgmt.db import Base


class MarkdownStatus(enum.StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


def _now() -> datetime:
    return datetime.now(UTC)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500))
    filename: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(200))
    size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    s3_key: Mapped[str] = mapped_column(String(1024))
    markdown_status: Mapped[MarkdownStatus] = mapped_column(
        Enum(MarkdownStatus, native_enum=False, length=20), default=MarkdownStatus.PENDING
    )
    markdown_s3_key: Mapped[str | None] = mapped_column(String(1024), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
