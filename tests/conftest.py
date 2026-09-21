import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient


def _async_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    return database_url


test_database_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
if not test_database_url:
    pytest.skip(
        "PostgreSQL integration tests require TEST_DATABASE_URL or an expressly set DATABASE_URL",
        allow_module_level=True,
    )

os.environ["DATABASE_URL"] = _async_database_url(test_database_url)

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
            yield test_client
