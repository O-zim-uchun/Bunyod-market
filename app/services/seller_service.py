from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.favorite import Favorite
from app.models.product import Product
from app.models.seller import Seller
from app.models.seller_content import SellerContent
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
    async def get_by_channel_id(session: AsyncSession, channel_id: int) -> Seller | None:
        result = await session.execute(select(Seller).where(Seller.channel_id == channel_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def create_seller(
        session: AsyncSession, telegram_id: int, name: str, channel_id: int | None = None
    ) -> Seller:
        existing_seller_result = await session.execute(select(Seller).where(Seller.telegram_id == telegram_id))
        seller = existing_seller_result.scalar_one_or_none()

        if seller is None:
            seller = Seller(name=name, telegram_id=telegram_id, channel_id=channel_id)
            session.add(seller)
            await session.flush()
        else:
            seller.name = name
            if channel_id is not None:
                seller.channel_id = channel_id
            seller.is_active = True
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

        await session.execute(delete(Favorite).where(Favorite.seller_id == seller_id))
        await session.execute(delete(SellerContent).where(SellerContent.seller_id == seller_id))
        await session.execute(update(Product).where(Product.seller_id == seller_id).values(seller_id=None))

        users = await session.execute(select(User).where(User.seller_id == seller_id))
        for user in users.scalars().all():
            user.seller_id = None
            if user.role == "seller":
                user.role = "user"

        await session.delete(seller)
        await session.flush()
        return True
