from collections.abc import Iterator
from typing import BinaryIO

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
