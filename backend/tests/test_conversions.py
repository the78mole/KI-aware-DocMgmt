import uuid

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from docmgmt.converter import ConversionResult
from docmgmt.worker import run_once
from tests.fakes import FakeConverter, InMemoryStorage
from tests.test_documents import upload


def convert_all(engine: Engine, storage: InMemoryStorage, converter: FakeConverter) -> None:
    while run_once(engine, storage, converter):
        pass


def test_markdown_404_until_converted(client: TestClient) -> None:
    document = upload(client).json()

    assert client.get(f"/api/documents/{document['id']}/markdown").status_code == 404


def test_markdown_and_assets_after_conversion(client: TestClient, engine: Engine, storage: InMemoryStorage) -> None:
    document = upload(client).json()
    converter = FakeConverter(
        ConversionResult(markdown="# LM317\n![](_page_0_Picture_1.jpeg)\n", images={"_page_0_Picture_1.jpeg": b"jpg"})
    )
    convert_all(engine, storage, converter)

    markdown = client.get(f"/api/documents/{document['id']}/markdown")
    conversion_id = markdown.headers["x-conversion-id"]
    asset = client.get(f"/api/documents/{document['id']}/conversions/{conversion_id}/assets/_page_0_Picture_1.jpeg")

    assert markdown.text.startswith("# LM317")
    assert markdown.headers["content-type"] == "text/markdown; charset=utf-8"
    assert asset.content == b"jpg"
    assert asset.headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/documents/{document['id']}").json()["conversion_status"] == "done"


def test_unknown_asset_returns_404(client: TestClient, engine: Engine, storage: InMemoryStorage) -> None:
    document = upload(client).json()
    convert_all(engine, storage, FakeConverter())
    conversion_id = client.get(f"/api/documents/{document['id']}/conversions").json()[0]["id"]

    base = f"/api/documents/{document['id']}/conversions"
    assert client.get(f"{base}/{conversion_id}/assets/fehlt.png").status_code == 404
    assert client.get(f"{base}/{uuid.uuid4()}/assets/x.png").status_code == 404
    assert client.get(f"/api/documents/{uuid.uuid4()}/conversions/{conversion_id}/assets/x.png").status_code == 404


def test_request_conversion_conflicts_while_pending(client: TestClient) -> None:
    document = upload(client).json()

    assert client.post(f"/api/documents/{document['id']}/conversions").status_code == 409


def test_reconversion_keeps_history_and_serves_latest(
    client: TestClient, engine: Engine, storage: InMemoryStorage
) -> None:
    document = upload(client).json()
    convert_all(engine, storage, FakeConverter(ConversionResult(markdown="alt")))

    response = client.post(f"/api/documents/{document['id']}/conversions")
    convert_all(engine, storage, FakeConverter(ConversionResult(markdown="neu")))

    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    conversions = client.get(f"/api/documents/{document['id']}/conversions").json()
    assert [c["status"] for c in conversions] == ["done", "done"]
    assert client.get(f"/api/documents/{document['id']}/markdown").text == "neu"


def test_markdown_falls_back_to_last_successful_conversion(
    client: TestClient, engine: Engine, storage: InMemoryStorage
) -> None:
    document = upload(client).json()
    convert_all(engine, storage, FakeConverter(ConversionResult(markdown="gut")))
    client.post(f"/api/documents/{document['id']}/conversions")
    convert_all(engine, storage, FakeConverter(error=RuntimeError("kaputt")))

    assert client.get(f"/api/documents/{document['id']}").json()["conversion_status"] == "failed"
    assert client.get(f"/api/documents/{document['id']}/markdown").text == "gut"


def test_conversions_of_unknown_document_return_404(client: TestClient) -> None:
    assert client.get(f"/api/documents/{uuid.uuid4()}/conversions").status_code == 404
    assert client.post(f"/api/documents/{uuid.uuid4()}/conversions").status_code == 404


def test_status_is_stored_as_lowercase_value(client: TestClient, engine: Engine) -> None:
    # Werte statt Enum-Namen, damit SQL-Abfragen von außen lesbar bleiben
    upload(client)

    with engine.connect() as connection:
        assert connection.scalar(text("SELECT status FROM conversions")) == "pending"
