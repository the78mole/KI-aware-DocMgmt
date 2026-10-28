from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine, create_engine

from docmgmt.api import documents
from docmgmt.config import Settings, get_settings
from docmgmt.db import Base
from docmgmt.storage import ObjectStorage, S3Storage


def create_app(
    settings: Settings | None = None, engine: Engine | None = None, storage: ObjectStorage | None = None
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.engine = engine or create_engine(settings.database_url, pool_pre_ping=True)
        app.state.storage = storage or S3Storage.from_settings(settings)
        # Bis Alembic eingeführt ist, legt der Start fehlende Tabellen an
        Base.metadata.create_all(app.state.engine)
        yield
        if engine is None:
            app.state.engine.dispose()

    app = FastAPI(title="KI-aware-DocMgmt", lifespan=lifespan)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(documents.router)

    if settings.static_dir and Path(settings.static_dir).is_dir():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="spa")

    return app


app = create_app()
