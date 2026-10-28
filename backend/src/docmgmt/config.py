from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Laufzeitkonfiguration, aus Umgebungsvariablen gelesen (z. B. aus dem Compose-Stack)."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = "postgresql+psycopg://docmgmt:docmgmt@127.0.0.1:5432/docmgmt"

    s3_endpoint_url: str = "http://127.0.0.1:3900"
    s3_region: str = "garage"
    s3_bucket: str = "docmgmt"
    s3_access_key_id: str = ""
    s3_secret_access_key: SecretStr = SecretStr("")

    # Verzeichnis mit der gebauten SPA; leer = keine statischen Dateien ausliefern
    static_dir: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
