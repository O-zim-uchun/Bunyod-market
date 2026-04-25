from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.favorite import Favorite
from app.models.product import Product


class FavoriteService:
    @staticmethod
    async def toggle(
        session: AsyncSession,
        user_id: int,
        seller_id: int,
        product_id: int,
    ) -> bool:
        row = await session.execute(
            select(Favorite).where(
                Favorite.user_id == user_id,
                Favorite.product_id == product_id,
            )
        )
        existing = row.scalar_one_or_none()
        if existing is None:
            session.add(Favorite(user_id=user_id, seller_id=seller_id, product_id=product_id))
            await session.flush()
            return True

        await session.delete(existing)
        await session.flush()
        return False

    @staticmethod
    async def list_by_seller(session: AsyncSession, user_id: int, seller_id: int) -> list[Product]:
        rows = await session.execute(
            select(Product)
            .join(Favorite, Favorite.product_id == Product.id)
            .where(Favorite.user_id == user_id, Favorite.seller_id == seller_id)
            .order_by(Product.created_at.desc(), Product.id.desc())
        )
        return list(rows.scalars().all())
