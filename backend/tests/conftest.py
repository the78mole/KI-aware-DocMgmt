from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from docmgmt.config import Settings
from docmgmt.main import create_app
from tests.fakes import InMemoryStorage


@pytest.fixture
def storage() -> InMemoryStorage:
    return InMemoryStorage()


@pytest.fixture
def client(storage: InMemoryStorage) -> Iterator[TestClient]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    app = create_app(Settings(), engine=engine, storage=storage)
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()
