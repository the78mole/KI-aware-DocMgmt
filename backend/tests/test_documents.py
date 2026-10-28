import hashlib
import uuid

from fastapi.testclient import TestClient

from tests.fakes import InMemoryStorage

PDF = b"%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n"


def upload(client: TestClient, content: bytes = PDF, filename: str = "LM317.pdf", **data: str):
    return client.post("/api/documents", files={"file": (filename, content, "application/pdf")}, data=data)


def test_upload_stores_pdf_and_metadata(client: TestClient, storage: InMemoryStorage) -> None:
    response = upload(client, title="  LM317 Spannungsregler ")

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "LM317 Spannungsregler"
    assert body["filename"] == "LM317.pdf"
    assert body["size"] == len(PDF)
    assert body["sha256"] == hashlib.sha256(PDF).hexdigest()
    assert body["markdown_status"] == "pending"
    assert storage.objects[f"documents/{body['id']}/original.pdf"] == (PDF, "application/pdf")


def test_upload_uses_filename_stem_as_default_title(client: TestClient) -> None:
    response = upload(client, filename="../../etc/NE555.pdf")

    assert response.json()["title"] == "NE555"
    assert response.json()["filename"] == "NE555.pdf"


def test_upload_rejects_non_pdf(client: TestClient, storage: InMemoryStorage) -> None:
    response = client.post("/api/documents", files={"file": ("notes.txt", b"hallo", "text/plain")})

    assert response.status_code == 415
    assert storage.objects == {}


def test_upload_rejects_empty_file(client: TestClient) -> None:
    assert upload(client, content=b"").status_code == 422


def test_upload_rejects_duplicate(client: TestClient, storage: InMemoryStorage) -> None:
    first = upload(client).json()

    response = upload(client, filename="kopie.pdf")

    assert response.status_code == 409
    assert response.json()["detail"]["document_id"] == first["id"]
    assert len(storage.objects) == 1


def test_list_documents_newest_first(client: TestClient) -> None:
    first = upload(client, content=PDF + b"1").json()
    second = upload(client, content=PDF + b"2").json()

    response = client.get("/api/documents")

    assert [d["id"] for d in response.json()] == [second["id"], first["id"]]


def test_get_document(client: TestClient) -> None:
    created = upload(client).json()

    assert client.get(f"/api/documents/{created['id']}").json() == created


def test_get_unknown_document_returns_404(client: TestClient) -> None:
    assert client.get(f"/api/documents/{uuid.uuid4()}").status_code == 404


def test_download_returns_original_file(client: TestClient) -> None:
    created = upload(client).json()

    response = client.get(f"/api/documents/{created['id']}/file")

    assert response.status_code == 200
    assert response.content == PDF
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == "inline; filename*=UTF-8''LM317.pdf"


def test_download_encodes_non_ascii_filename(client: TestClient) -> None:
    created = upload(client, filename="Übersicht µC.pdf").json()

    response = client.get(f"/api/documents/{created['id']}/file")

    assert response.headers["content-disposition"] == "inline; filename*=UTF-8''%C3%9Cbersicht%20%C2%B5C.pdf"


def test_download_missing_object_returns_404(client: TestClient, storage: InMemoryStorage) -> None:
    created = upload(client).json()
    storage.objects.clear()

    assert client.get(f"/api/documents/{created['id']}/file").status_code == 404
