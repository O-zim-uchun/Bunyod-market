from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserService:
    @staticmethod
    async def get_or_create(session: AsyncSession, telegram_id: int, admin_id: int | None = None) -> User:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()

        if user is None:
            role = "super_admin" if admin_id is not None and telegram_id == admin_id else "user"
            user = User(telegram_id=telegram_id, role=role)
            session.add(user)
            await session.flush()
            return user

        if admin_id is not None and telegram_id == admin_id and user.role != "super_admin":
            user.role = "super_admin"
            await session.flush()

        return user
