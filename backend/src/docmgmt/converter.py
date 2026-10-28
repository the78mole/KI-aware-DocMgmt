import base64
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Any, Protocol

import httpx


class ConversionError(Exception):
    pass


@dataclass
class ConversionResult:
    markdown: str
    meta: dict[str, Any] = field(default_factory=dict)
    images: dict[str, bytes] = field(default_factory=dict)


class Converter(Protocol):
    name: str

    def convert(self, pdf: bytes, filename: str) -> ConversionResult: ...


class MarkerServerConverter:
    """Spricht die HTTP-API von `marker_server` (POST /marker/upload)."""

    def __init__(
        self,
        base_url: str,
        name: str,
        mode: str | None = None,
        timeout: float = 1800.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.name = name
        self._mode = mode
        self._client = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)

    def convert(self, pdf: bytes, filename: str) -> ConversionResult:
        data = {"output_format": "markdown"}
        if self._mode:
            data["mode"] = self._mode
        try:
            response = self._client.post(
                "/marker/upload", files={"file": (filename, pdf, "application/pdf")}, data=data
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ConversionError(f"marker nicht erreichbar oder fehlerhaft: {exc}") from exc

        body = response.json()
        if not body.get("success"):
            raise ConversionError(body.get("error") or "marker meldet einen unbekannten Fehler")
        images = {}
        for name, encoded in (body.get("images") or {}).items():
            # marker liefert flache Namen; Pfadanteile verwerfen, damit kein Schlüssel ausbricht
            images[PurePath(name).name] = base64.b64decode(encoded)
        return ConversionResult(markdown=body.get("output") or "", meta=body.get("metadata") or {}, images=images)
