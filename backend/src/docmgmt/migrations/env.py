from alembic import context
from sqlalchemy import create_engine

from docmgmt import models  # noqa: F401  registriert die Tabellen in Base.metadata
from docmgmt.config import get_settings
from docmgmt.db import Base

config = context.config


def run_migrations() -> None:
    # migrate() reicht eine offene Verbindung durch, die CLI baut sich eine aus DATABASE_URL
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    with create_engine(get_settings().database_url).connect() as connection:
        _run(connection)


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


run_migrations()
