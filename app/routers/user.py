from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.db.session import get_session
from app.services.product_service import ProductService
from app.services.seller_service import SellerService
from app.services.user_service import UserService

router = Router(name="user_router")


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    async with get_session() as session:
        user = await UserService.get_or_create(session, message.from_user.id)
        await session.commit()

        if user.role == "super_admin":
            await message.answer("Admin panel\nBuyruqlar: /admin_sellers")
            return

        if user.role == "seller":
            await message.answer("Seller panel\nBuyruqlar: /warehouse, /delete_product <id>")
            return

        sellers = await SellerService.list_active_sellers(session)

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


@router.callback_query(lambda c: c.data and c.data.startswith("seller_select:"))
async def seller_select(callback) -> None:
    seller_id = int(callback.data.split(":", maxsplit=1)[1])

    async with get_session() as session:
        products = await ProductService.list_products_by_seller(session, seller_id)

    if not products:
        await callback.message.answer("Bu sellerda mahsulotlar hali yo'q.")
    else:
        ids = ", ".join(str(product.id) for product in products)
        await callback.message.answer(f"Seller mahsulotlari: {ids}")

    await callback.answer()
