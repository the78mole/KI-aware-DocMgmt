import base64

import httpx
import pytest

from docmgmt.converter import ConversionError, MarkerServerConverter


def converter_with(handler, mode: str | None = "fast") -> MarkerServerConverter:
    return MarkerServerConverter("http://marker", "marker-pdf 2.0.0", mode=mode, transport=httpx.MockTransport(handler))


def test_convert_posts_pdf_and_decodes_result() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "success": True,
                "output": "# LM317",
                "metadata": {"table_of_contents": []},
                "images": {"../../a.jpeg": base64.b64encode(b"jpg").decode()},
            },
        )

    result = converter_with(handler).convert(b"%PDF", "doc.pdf")

    assert seen[0].url.path == "/marker/upload"
    body = seen[0].content
    assert b'name="mode"' in body and b"fast" in body and b"%PDF" in body
    assert result.markdown == "# LM317"
    assert result.meta == {"table_of_contents": []}
    assert result.images == {"a.jpeg": b"jpg"}


def test_convert_without_mode_omits_field() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert b'name="mode"' not in request.content
        return httpx.Response(200, json={"success": True, "output": "x"})

    result = converter_with(handler, mode=None).convert(b"%PDF", "doc.pdf")

    assert result.images == {} and result.meta == {}


def test_marker_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": False, "error": "kein PDF"})

    with pytest.raises(ConversionError, match="kein PDF"):
        converter_with(handler).convert(b"x", "doc.pdf")


def test_http_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with pytest.raises(ConversionError, match="nicht erreichbar"):
        converter_with(handler).convert(b"x", "doc.pdf")
