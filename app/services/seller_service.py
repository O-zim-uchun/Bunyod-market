from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.seller import Seller


class SellerService:
    @staticmethod
    async def list_active_sellers(session: AsyncSession) -> list[Seller]:
        result = await session.execute(select(Seller).where(Seller.is_active.is_(True)).order_by(Seller.id.asc()))
        return list(result.scalars().all())

    @staticmethod
    async def list_all_sellers(session: AsyncSession) -> list[Seller]:
        result = await session.execute(select(Seller).order_by(Seller.id.asc()))
        return list(result.scalars().all())
