from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.seller_content import SellerContent


class SellerContentService:
    @staticmethod
    async def set_content(
        session: AsyncSession,
        seller_id: int,
        content_type: str,
        channel_id: int | None,
        message_id: int | None,
    ) -> SellerContent:
        existing = await session.execute(
            select(SellerContent).where(
                SellerContent.seller_id == seller_id,
                SellerContent.content_type == content_type,
            )
        )
        row = existing.scalar_one_or_none()
        if row is None:
            row = SellerContent(
                seller_id=seller_id,
                content_type=content_type,
                channel_id=channel_id,
                message_id=message_id,
            )
            session.add(row)
        else:
            row.channel_id = channel_id
            row.message_id = message_id

        await session.flush()
        return row

    @staticmethod
    async def get_content(session: AsyncSession, seller_id: int, content_type: str) -> SellerContent | None:
        result = await session.execute(
            select(SellerContent).where(
                SellerContent.seller_id == seller_id,
                SellerContent.content_type == content_type,
            )
        )
        return result.scalar_one_or_none()
