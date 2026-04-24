from os import getenv

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_session
from app.services.product_service import ProductService
from app.services.seller_service import SellerService
from app.services.user_service import UserService

router = Router(name="user_router")


def _admin_id() -> int | None:
    value = getenv("ADMIN_ID")
    if value and value.isdigit():
        return int(value)
    return None


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    try:
        async with get_session() as session:
            user = await UserService.get_or_create(session, message.from_user.id, admin_id=_admin_id())
            await session.commit()

            if user.role == "super_admin":
                await message.answer("📊 Admin panel\n/admin")
                return

            if user.role == "seller":
                await message.answer("📦 Seller panel\n/seller\n/warehouse")
                return

            sellers = await SellerService.list_active_sellers(session)
    except SQLAlchemyError:
        await message.answer("DB bilan bog'lanishda xatolik. Keyinroq urinib ko'ring.")
        return
    except RuntimeError as exc:
        await message.answer(str(exc))
        return

    if not sellers:
        await message.answer("Hozircha faol sellerlar yo'q.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=seller.name, callback_data=f"seller_select:{seller.id}")]
            for seller in sellers
        ]
    )
    await message.answer("Do'konni tanlang:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("seller_select:"))
async def seller_select(callback: CallbackQuery) -> None:
    seller_id = int(callback.data.split(":", maxsplit=1)[1])

    try:
        async with get_session() as session:
            products = await ProductService.list_products_by_seller(session, seller_id)
    except SQLAlchemyError:
        await callback.message.answer("Mahsulotlarni olishda xatolik.")
        await callback.answer()
        return

    if not products:
        await callback.message.answer("Bu sellerda mahsulotlar hali yo'q.")
    else:
        ids = ", ".join(str(product.id) for product in products)
        await callback.message.answer(f"Seller mahsulotlari: {ids}")

    await callback.answer()
