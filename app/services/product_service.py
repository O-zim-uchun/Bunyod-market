from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product import Product
from app.models.seller import Seller
from app.models.user import User


CATEGORIES: dict[str, str] = {
    "telefon": "📱 Telefon",
    "texnika": "💻 Texnika",
    "kiyim": "👕 Kiyim",
    "boshqa": "🏠 Boshqa",
}


class ProductAccessError(PermissionError):
    """Raised when a user tries to access a product outside their permissions."""


class ProductService:
    @staticmethod
    def _apply_role_filter(stmt: Select[tuple[Product]], user: User) -> Select[tuple[Product]]:
        if user.role == "seller":
            return stmt.where(Product.seller_id == user.seller_id)
        return stmt

    @classmethod
    async def list_products(cls, session: AsyncSession, user: User) -> list[Product]:
        stmt = cls._apply_role_filter(select(Product), user)
        result = await session.execute(stmt.order_by(Product.created_at.desc(), Product.id.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def list_all_with_seller(session: AsyncSession) -> list[Product]:
        result = await session.execute(
            select(Product).options(selectinload(Product.seller)).order_by(Product.created_at.desc(), Product.id.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_products_by_seller(session: AsyncSession, seller_id: int) -> list[Product]:
        result = await session.execute(
            select(Product)
            .where(Product.seller_id == seller_id)
            .order_by(Product.created_at.desc(), Product.id.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_seller_categories(session: AsyncSession, seller_id: int) -> list[str]:
        result = await session.execute(
            select(distinct(Product.category))
            .where(Product.seller_id == seller_id, Product.category.is_not(None))
            .order_by(Product.category.asc())
        )
        return [row[0] for row in result.all() if row[0]]

    @staticmethod
    async def list_seller_products_by_category(session: AsyncSession, seller_id: int, category: str) -> list[Product]:
        result = await session.execute(
            select(Product)
            .where(Product.seller_id == seller_id, Product.category == category)
            .order_by(Product.created_at.desc(), Product.id.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_products_by_seller_category(
        session: AsyncSession,
        seller_id: int,
        category: str,
        page: int,
        page_size: int = 5,
    ) -> tuple[list[Product], int]:
        total_result = await session.execute(
            select(func.count(Product.id)).where(Product.seller_id == seller_id, Product.category == category)
        )
        total = int(total_result.scalar() or 0)

        offset = max(page - 1, 0) * page_size
        rows = await session.execute(
            select(Product)
            .where(Product.seller_id == seller_id, Product.category == category)
            .order_by(Product.created_at.desc(), Product.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(rows.scalars().all()), total

    @staticmethod
    async def list_new_arrivals(session: AsyncSession, seller_id: int, page: int, page_size: int = 5) -> tuple[list[Product], int]:
        threshold = datetime.now(timezone.utc) - timedelta(days=10)
        total_result = await session.execute(
            select(func.count(Product.id)).where(Product.seller_id == seller_id, Product.created_at >= threshold)
        )
        total = int(total_result.scalar() or 0)

        offset = max(page - 1, 0) * page_size
        rows = await session.execute(
            select(Product)
            .where(Product.seller_id == seller_id, Product.created_at >= threshold)
            .order_by(Product.created_at.desc(), Product.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(rows.scalars().all()), total

    @staticmethod
    async def seller_product_count(session: AsyncSession, seller_id: int) -> int:
        result = await session.execute(select(func.count(Product.id)).where(Product.seller_id == seller_id))
        return int(result.scalar() or 0)

    @classmethod
    async def create_product(
        cls,
        session: AsyncSession,
        user: User,
        **product_payload: object,
    ) -> Product:
        if user.role == "seller":
            product_payload["seller_id"] = user.seller_id

        product = Product(**product_payload)
        session.add(product)
        await session.flush()
        return product

    @staticmethod
    async def create_or_update_from_channel(
        session: AsyncSession,
        seller: Seller,
        channel_id: int,
        message_id: int,
    ) -> Product:
        existing = await session.execute(
            select(Product).where(Product.channel_id == channel_id, Product.message_id == message_id)
        )
        product = existing.scalar_one_or_none()

        if product is None:
            product = Product(
                seller_id=seller.id,
                channel_id=channel_id,
                message_id=message_id,
                category=None,
            )
            session.add(product)
        else:
            product.seller_id = seller.id

        await session.flush()
        return product

    @staticmethod
    async def set_category(session: AsyncSession, product_id: int, category: str) -> Product | None:
        product = await session.get(Product, product_id)
        if product is None:
            return None

        product.category = category
        await session.flush()
        return product

    @staticmethod
    def ensure_manage_permission(user: User, product: Product) -> None:
        if user.role == "super_admin":
            return
        if user.role == "seller" and product.seller_id == user.seller_id:
            return
        raise ProductAccessError("You can only manage your own products.")

    @classmethod
    async def get_product_for_update(cls, session: AsyncSession, user: User, product_id: int) -> Product:
        product = await session.get(Product, product_id)
        if product is None:
            raise LookupError("Product not found")

        cls.ensure_manage_permission(user, product)
        return product

    @classmethod
    async def delete_product(cls, session: AsyncSession, user: User, product_id: int) -> Product:
        product = await cls.get_product_for_update(session, user, product_id)
        await session.delete(product)
        await session.flush()
        return product
