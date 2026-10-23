"""Shared test fixtures.

Time is pinned: ``FIXED_NOW`` is a Monday, and the API's clock is overridden to
return it. That makes "in the past", "within the next hour" and "which weekday
is this" deterministic instead of dependent on when the suite runs.
"""

from __future__ import annotations

import os

os.environ.setdefault(
    "TEST_DATABASE_URL", "postgresql+asyncpg://clinic:clinic@localhost:55432/clinic_test"
)
os.environ.setdefault("DATABASE_URL", os.environ["TEST_DATABASE_URL"])

from collections.abc import AsyncIterator  # noqa: E402

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from app.api.deps import get_now  # noqa: E402
from app.core.db import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from tests.helpers import FIXED_NOW  # noqa: E402

TEST_URL = os.environ["TEST_DATABASE_URL"]


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    # NullPool: pytest-asyncio runs each test in its own event loop, and a
    # pooled asyncpg connection may not cross loops. Each acquire gets a fresh
    # connection instead.
    engine = create_async_engine(TEST_URL, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(engine: AsyncEngine) -> AsyncIterator[None]:
    async with engine.begin() as connection:
        await connection.execute(
            text("TRUNCATE TABLE appointments, doctor_schedules, patients, doctors CASCADE")
        )
    yield


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session


@pytest_asyncio.fixture
async def client(engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_now] = lambda: FIXED_NOW

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
