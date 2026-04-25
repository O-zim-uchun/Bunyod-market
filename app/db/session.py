from __future__ import annotations

from contextlib import asynccontextmanager
from os import getenv

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base

DATABASE_URL = getenv("DATABASE_URL") or getenv("POSTGRES_URL")

_session_factory: async_sessionmaker[AsyncSession] | None = None
_engine = None

if DATABASE_URL:
    _engine = create_async_engine(DATABASE_URL, future=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def _ensure_runtime_columns() -> None:
    """Lightweight compatibility DDL for old DBs where migrations were not executed."""
    if _engine is None:
        return

    statements = [
        # users
        "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user'",
        "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS seller_id BIGINT NULL",
        "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS telegram_id BIGINT NULL",
        # products
        "ALTER TABLE IF EXISTS products ADD COLUMN IF NOT EXISTS seller_id BIGINT NULL",
        "ALTER TABLE IF EXISTS products ADD COLUMN IF NOT EXISTS channel_id BIGINT NULL",
        "ALTER TABLE IF EXISTS products ADD COLUMN IF NOT EXISTS message_id BIGINT NULL",
        "ALTER TABLE IF EXISTS products ADD COLUMN IF NOT EXISTS category VARCHAR(64) NULL",
        "ALTER TABLE IF EXISTS products ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        # sellers
        "CREATE TABLE IF NOT EXISTS sellers (id BIGSERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, telegram_id BIGINT NOT NULL UNIQUE, channel_id BIGINT NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS seller_contents (id BIGSERIAL PRIMARY KEY, seller_id BIGINT NOT NULL REFERENCES sellers(id) ON DELETE CASCADE, content_type VARCHAR(32) NOT NULL, channel_id BIGINT NULL, message_id BIGINT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), CONSTRAINT uq_seller_content_type UNIQUE (seller_id, content_type))",
        "CREATE TABLE IF NOT EXISTS favorites (id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE, seller_id BIGINT NOT NULL REFERENCES sellers(id) ON DELETE CASCADE, product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), CONSTRAINT uq_favorite_user_product UNIQUE (user_id, product_id))",
    ]

    async with _engine.begin() as conn:
        for stmt in statements:
            await conn.execute(text(stmt))

        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_telegram_id ON users (telegram_id) WHERE telegram_id IS NOT NULL"
            )
        )


async def init_models() -> None:
    if _engine is None:
        raise RuntimeError("DATABASE_URL (yoki POSTGRES_URL) Railway Variables'da o'rnatilmagan")

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _ensure_runtime_columns()


@asynccontextmanager
async def get_session() -> AsyncSession:
    if _session_factory is None:
        raise RuntimeError("DATABASE_URL (yoki POSTGRES_URL) Railway Variables'da o'rnatilmagan")

    async with _session_factory() as session:
        yield session
