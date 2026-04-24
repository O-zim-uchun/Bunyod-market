from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.seller import Seller
from app.models.user import User


class SellerService:
    @staticmethod
    async def list_active_sellers(session: AsyncSession) -> list[Seller]:
        result = await session.execute(select(Seller).where(Seller.is_active.is_(True)).order_by(Seller.id.asc()))
        return list(result.scalars().all())

    @staticmethod
    async def list_all_sellers(session: AsyncSession) -> list[Seller]:
        result = await session.execute(select(Seller).order_by(Seller.id.asc()))
        return list(result.scalars().all())

    @staticmethod
    async def create_seller(session: AsyncSession, telegram_id: int, name: str) -> Seller:
        seller = Seller(name=name, telegram_id=telegram_id)
        session.add(seller)
        await session.flush()

        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(telegram_id=telegram_id, role="seller", seller_id=seller.id)
            session.add(user)
        else:
            user.role = "seller"
            user.seller_id = seller.id

        await session.flush()
        return seller

    @staticmethod
    async def delete_seller(session: AsyncSession, seller_id: int) -> bool:
        seller = await session.get(Seller, seller_id)
        if seller is None:
            return False

        users = await session.execute(select(User).where(User.seller_id == seller_id))
        for user in users.scalars().all():
            user.seller_id = None
            if user.role == "seller":
                user.role = "user"

        await session.delete(seller)
        await session.flush()
        return True
