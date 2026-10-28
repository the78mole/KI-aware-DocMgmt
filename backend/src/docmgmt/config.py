from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from docmgmt.openbao import with_openbao


class Settings(BaseSettings):
    """Laufzeitkonfiguration aus Umgebungsvariablen, optional ergänzt aus OpenBao (siehe docmgmt.openbao)."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return with_openbao(settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings)

    database_url: str = "postgresql+psycopg://docmgmt:docmgmt@127.0.0.1:5432/docmgmt"

    s3_endpoint_url: str = "http://127.0.0.1:3900"
    s3_region: str = "garage"
    s3_bucket: str = "docmgmt"
    s3_access_key_id: str = ""
    s3_secret_access_key: SecretStr = SecretStr("")

    # marker_server (CPU-Container im Stack, später holy-moly-mcp)
    marker_url: str = "http://127.0.0.1:8001"
    marker_label: str = "marker-pdf 2.0.0"
    # "fast" = CPU-Layout, kaum VLM; leer = marker entscheidet nach Gerät
    marker_mode: str = "fast"
    conversion_timeout_seconds: int = 3600
    worker_poll_seconds: float = 5.0

    # Verzeichnis mit der gebauten SPA; leer = keine statischen Dateien ausliefern
    static_dir: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
