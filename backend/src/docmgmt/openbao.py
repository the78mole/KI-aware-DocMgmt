"""Optionale Secret-Quelle: liest Einstellungen aus OpenBao bzw. Vault (KV v2).

Aktiv nur, wenn `BAO_SECRET_PATH` gesetzt ist. Ein bloßes `BAO_TOKEN` in der Shell schaltet sie also nicht ein.
Die Schlüssel im KV-Eintrag heißen wie die Einstellungen (`s3_secret_access_key`, `database_url`, …).
Umgebungsvariablen haben Vorrang, OpenBao füllt nur, was dort fehlt.
"""

import os
from typing import Any

import httpx
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource


class OpenBaoError(RuntimeError):
    pass


def _env(*names: str) -> str:
    return next((os.environ[n] for n in names if os.environ.get(n)), "")


def read_kv(addr: str, token: str, path: str, namespace: str = "", timeout: float = 10.0) -> dict[str, Any]:
    """Liest einen KV-v2-Eintrag, `path` inklusive Mount, z. B. `secret/ki-aware-docmgmt`."""
    mount, _, name = path.strip("/").partition("/")
    if not name:
        raise OpenBaoError(f"BAO_SECRET_PATH {path!r} braucht die Form <mount>/<pfad>")
    headers = {"X-Vault-Token": token}
    if namespace:
        headers["X-Vault-Namespace"] = namespace
    url = f"{addr.rstrip('/')}/v1/{mount}/data/{name}"
    try:
        response = httpx.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()["data"]["data"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise OpenBaoError(f"OpenBao-Eintrag {path!r} nicht lesbar: {exc}") from exc


class OpenBaoSettingsSource(PydanticBaseSettingsSource):
    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:  # pragma: no cover
        # Wird von pydantic-settings nicht aufgerufen, weil __call__ überschrieben ist
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        paths = [p.strip() for p in _env("BAO_SECRET_PATH").split(",") if p.strip()]
        if not paths:
            return {}
        addr = _env("BAO_ADDR", "VAULT_ADDR")
        token = _env("BAO_TOKEN", "VAULT_TOKEN")
        if not addr or not token:
            raise OpenBaoError("BAO_SECRET_PATH ist gesetzt, aber BAO_ADDR oder BAO_TOKEN fehlt")
        namespace = _env("BAO_NAMESPACE", "VAULT_NAMESPACE")

        fields = self.settings_cls.model_fields
        values: dict[str, Any] = {}
        for path in paths:  # spätere Pfade überschreiben frühere
            data = read_kv(addr, token, path, namespace)
            values.update({key: value for key, value in data.items() if key in fields})
        return values


def with_openbao(
    settings_cls: type[BaseSettings],
    init_settings: PydanticBaseSettingsSource,
    env_settings: PydanticBaseSettingsSource,
    dotenv_settings: PydanticBaseSettingsSource,
    file_secret_settings: PydanticBaseSettingsSource,
) -> tuple[PydanticBaseSettingsSource, ...]:
    return init_settings, env_settings, dotenv_settings, OpenBaoSettingsSource(settings_cls), file_secret_settings
