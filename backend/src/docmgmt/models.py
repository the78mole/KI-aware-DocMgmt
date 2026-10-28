import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from docmgmt.db import Base


class ConversionStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    conversions: Mapped[list["Conversion"]] = relationship(
        back_populates="document",
        order_by="Conversion.created_at.desc()",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    @property
    def latest_conversion(self) -> "Conversion | None":
        return self.conversions[0] if self.conversions else None

    @property
    def conversion_status(self) -> ConversionStatus | None:
        latest = self.latest_conversion
        return latest.status if latest else None


class Conversion(Base):
    """Ein Lauf der PDF→Markdown-Umwandlung. Markdown und Metadaten liegen hier, Bilder in S3."""

    __tablename__ = "conversions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    status: Mapped[ConversionStatus] = mapped_column(
        Enum(ConversionStatus, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        default=ConversionStatus.PENDING,
        index=True,
    )
    converter: Mapped[str | None] = mapped_column(String(200), default=None)
    markdown: Mapped[str | None] = mapped_column(Text, default=None)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), default=None)
    assets: Mapped[list[str]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), default=list)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    document: Mapped[Document] = relationship(back_populates="conversions")

    def asset_key(self, name: str) -> str:
        return f"documents/{self.document_id}/conversions/{self.id}/{name}"
