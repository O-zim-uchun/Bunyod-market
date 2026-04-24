from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserService:
    @staticmethod
    async def get_or_create(session: AsyncSession, telegram_id: int) -> User:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user:
            return user

        user = User(telegram_id=telegram_id, role="user")
        session.add(user)
        await session.flush()
        return user
