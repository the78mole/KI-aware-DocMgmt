from collections.abc import Iterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import Request
from sqlalchemy import Engine
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session


def migrate(engine: Engine) -> None:
    """Bringt das Schema per Alembic auf den neuesten Stand."""
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
