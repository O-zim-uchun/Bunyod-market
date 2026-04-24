from __future__ import annotations

from contextlib import asynccontextmanager
from os import getenv

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = getenv("DATABASE_URL") or getenv("POSTGRES_URL")

_session_factory: async_sessionmaker[AsyncSession] | None = None

if DATABASE_URL:
    engine = create_async_engine(DATABASE_URL, future=True)
    _session_factory = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def get_session() -> AsyncSession:
    if _session_factory is None:
        raise RuntimeError("DATABASE_URL (yoki POSTGRES_URL) Railway Variables'da o'rnatilmagan")

    async with _session_factory() as session:
        yield session
