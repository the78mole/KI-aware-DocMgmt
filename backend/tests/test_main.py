from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from docmgmt.config import Settings
from docmgmt.main import create_app
from tests.fakes import InMemoryStorage


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_serves_spa_from_static_dir(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>SPA</h1>")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    app = create_app(Settings(static_dir=str(tmp_path)), engine=engine, storage=InMemoryStorage())
    with TestClient(app) as client:
        assert client.get("/").text == "<h1>SPA</h1>"
        assert client.get("/api/health").json() == {"status": "ok"}
    engine.dispose()
