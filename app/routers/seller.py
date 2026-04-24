from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.db.session import get_session
from app.services.product_service import ProductAccessError, ProductService
from app.services.user_service import UserService

router = Router(name="seller_router")


@router.message(Command("warehouse"))
async def seller_warehouse(message: Message) -> None:
    async with get_session() as session:
        user = await UserService.get_or_create(session, message.from_user.id)
        if user.role != "seller" or not user.seller_id:
            await message.answer("Siz seller emassiz.")
            return

        products = await ProductService.list_products(session, user)
        count = len(products)

    if not products:
        await message.answer("Sizning omborda mahsulot yo'q.")
        return

    ids = ", ".join(str(item.id) for item in products)
    await message.answer(f"Ombor: {count} ta mahsulot\nIDlar: {ids}")


@router.message(Command("delete_product"))
async def seller_delete_product(message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Format: /delete_product <product_id>")
        return

    product_id = int(parts[1])

    async with get_session() as session:
        user = await UserService.get_or_create(session, message.from_user.id)
        try:
            await ProductService.delete_product(session, user, product_id)
            await session.commit()
        except ProductAccessError:
            await session.rollback()
            await message.answer("Siz faqat o'zingizning mahsulotingizni o'chira olasiz.")
            return
        except LookupError:
            await session.rollback()
            await message.answer("Mahsulot topilmadi.")
            return

    await message.answer("Mahsulot o'chirildi.")
