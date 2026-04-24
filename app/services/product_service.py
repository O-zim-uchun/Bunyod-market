from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.user import User


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
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def list_products_by_seller(session: AsyncSession, seller_id: int) -> list[Product]:
        result = await session.execute(select(Product).where(Product.seller_id == seller_id))
        return list(result.scalars().all())

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
    async def delete_product(cls, session: AsyncSession, user: User, product_id: int) -> None:
        product = await cls.get_product_for_update(session, user, product_id)
        await session.delete(product)
        await session.flush()
