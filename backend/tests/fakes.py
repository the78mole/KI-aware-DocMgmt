from collections.abc import Iterator
from typing import BinaryIO

from docmgmt.converter import ConversionResult
from docmgmt.storage import ObjectNotFoundError


class InMemoryStorage:
    """Fake für ObjectStorage, hält Objekte im Speicher."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put(self, key: str, data: BinaryIO, content_type: str) -> None:
        self.objects[key] = (data.read(), content_type)

    def open(self, key: str) -> Iterator[bytes]:
        if key not in self.objects:
            raise ObjectNotFoundError(key)
        return iter([self.objects[key][0]])


class FakeConverter:
    """Fake für Converter: liefert ein festes Ergebnis oder wirft den hinterlegten Fehler."""

    name = "fake-marker 1.0"

    def __init__(self, result: ConversionResult | None = None, error: Exception | None = None) -> None:
        self.result = result or ConversionResult(markdown="# Datenblatt\n")
        self.error = error
        self.calls: list[tuple[bytes, str]] = []

    def convert(self, pdf: bytes, filename: str) -> ConversionResult:
        self.calls.append((pdf, filename))
        if self.error:
            raise self.error
        return self.result
