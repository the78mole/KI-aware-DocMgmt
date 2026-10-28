import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from docmgmt.config import Settings
from docmgmt.openbao import OpenBaoError, read_kv

TOKEN = "s.test"


class FakeOpenBao:
    """Minimaler KV-v2-Server: GET /v1/<mount>/data/<pfad> mit Token- und Namespace-Prüfung."""

    def __init__(self) -> None:
        self.entries: dict[str, dict] = {}
        self.namespaces: list[str | None] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                fake.namespaces.append(self.headers.get("X-Vault-Namespace"))
                entry = fake.entries.get(self.path)
                if self.headers.get("X-Vault-Token") != TOKEN:
                    self._reply(403, {"errors": ["permission denied"]})
                elif entry is None:
                    self._reply(404, {"errors": []})
                else:
                    self._reply(200, {"data": {"data": entry, "metadata": {"version": 1}}})

            def _reply(self, status: int, body: dict) -> None:
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args) -> None:
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.addr = f"http://127.0.0.1:{self.server.server_port}"

    def put(self, path: str, data: dict) -> None:
        mount, _, name = path.partition("/")
        self.entries[f"/v1/{mount}/data/{name}"] = data


@pytest.fixture
def bao(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeOpenBao]:
    fake = FakeOpenBao()
    thread = threading.Thread(target=fake.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    for name in ("BAO_ADDR", "BAO_TOKEN", "BAO_NAMESPACE", "BAO_SECRET_PATH", "VAULT_ADDR", "VAULT_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BAO_ADDR", fake.addr)
    monkeypatch.setenv("BAO_TOKEN", TOKEN)
    yield fake
    fake.server.shutdown()
    fake.server.server_close()


def test_inactive_without_secret_path(bao: FakeOpenBao) -> None:
    assert Settings().s3_access_key_id == ""
    assert bao.namespaces == []


def test_fills_settings_from_kv(bao: FakeOpenBao, monkeypatch: pytest.MonkeyPatch) -> None:
    bao.put("secret/docmgmt", {"s3_access_key_id": "GKabc", "s3_secret_access_key": "geheim", "notes": "ignoriert"})
    monkeypatch.setenv("BAO_SECRET_PATH", "secret/docmgmt")
    monkeypatch.setenv("BAO_NAMESPACE", "it-infra")

    settings = Settings()

    assert settings.s3_access_key_id == "GKabc"
    assert settings.s3_secret_access_key.get_secret_value() == "geheim"
    assert bao.namespaces == ["it-infra"]


def test_environment_wins_and_later_paths_override(bao: FakeOpenBao, monkeypatch: pytest.MonkeyPatch) -> None:
    bao.put("secret/s3", {"s3_access_key_id": "GKalt", "s3_bucket": "aus-bao"})
    bao.put("secret/s3-neu", {"s3_access_key_id": "GKneu"})
    monkeypatch.setenv("BAO_SECRET_PATH", "secret/s3, secret/s3-neu")
    monkeypatch.setenv("S3_BUCKET", "aus-env")

    settings = Settings()

    assert settings.s3_access_key_id == "GKneu"
    assert settings.s3_bucket == "aus-env"


def test_vault_variables_are_accepted(bao: FakeOpenBao, monkeypatch: pytest.MonkeyPatch) -> None:
    bao.put("kv/app", {"marker_url": "http://marker.intern"})
    monkeypatch.delenv("BAO_ADDR")
    monkeypatch.delenv("BAO_TOKEN")
    monkeypatch.setenv("VAULT_ADDR", bao.addr)
    monkeypatch.setenv("VAULT_TOKEN", TOKEN)
    monkeypatch.setenv("BAO_SECRET_PATH", "kv/app")

    assert Settings().marker_url == "http://marker.intern"
    assert bao.namespaces == [None]


def test_missing_token_fails_fast(bao: FakeOpenBao, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BAO_TOKEN")
    monkeypatch.setenv("BAO_SECRET_PATH", "secret/docmgmt")

    with pytest.raises(OpenBaoError, match="BAO_TOKEN fehlt"):
        Settings()


def test_unreadable_entry_fails_fast(bao: FakeOpenBao, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAO_SECRET_PATH", "secret/fehlt")

    with pytest.raises(OpenBaoError, match="nicht lesbar"):
        Settings()


def test_wrong_token_fails(bao: FakeOpenBao) -> None:
    with pytest.raises(OpenBaoError, match="403"):
        read_kv(bao.addr, "falsch", "secret/docmgmt")


def test_path_needs_mount_and_name() -> None:
    with pytest.raises(OpenBaoError, match="<mount>/<pfad>"):
        read_kv("http://127.0.0.1:1", TOKEN, "secret")
