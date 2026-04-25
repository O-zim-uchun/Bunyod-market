from math import ceil
from os import getenv

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_session
from app.services.product_service import CATEGORIES, ProductService
from app.services.seller_content_service import SellerContentService
from app.services.seller_service import SellerService
from app.services.user_service import UserService

router = Router(name="user_router")


def _admin_id() -> int | None:
    value = getenv("ADMIN_ID")
    if value and value.isdigit():
        return int(value)
    return None


def _seller_sections_keyboard(seller_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛍 Tovarlar", callback_data=f"user_shop:{seller_id}")],
            [InlineKeyboardButton(text="🔥 Yangi kelganlar", callback_data=f"user_new:{seller_id}:1")],
            [InlineKeyboardButton(text="💰 Aksiya", callback_data=f"user_promo:{seller_id}")],
            [InlineKeyboardButton(text="📞 Aloqa", callback_data=f"user_contact:{seller_id}")],
        ]
    )


def _categories_keyboard(seller_id: int, categories: list[str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=CATEGORIES.get(slug, slug), callback_data=f"user_cat:{seller_id}:{slug}:1")]
            for slug in categories
        ]
    )


def _pagination_keyboard(prefix: str, seller_id: int, key: str, page: int, pages: int) -> InlineKeyboardMarkup:
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"{prefix}:{seller_id}:{key}:{page - 1}"))
    buttons.append(InlineKeyboardButton(text=f"{page}/{pages}", callback_data="noop"))
    if page < pages:
        buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"{prefix}:{seller_id}:{key}:{page + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery) -> None:
    await callback.answer()


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
                await message.answer("📦 Seller panel\n/seller")
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
    await callback.message.answer("Bo'limni tanlang:", reply_markup=_seller_sections_keyboard(seller_id))
    await callback.answer()


@router.callback_query(F.data.startswith("user_shop:"))
async def user_shop_categories(callback: CallbackQuery) -> None:
    seller_id = int(callback.data.split(":", maxsplit=1)[1])
    try:
        async with get_session() as session:
            categories = await ProductService.list_seller_categories(session, seller_id)
    except (SQLAlchemyError, RuntimeError):
        await callback.answer("Xatolik", show_alert=True)
        return

    if not categories:
        await callback.message.answer("Bu do'konda hali kategoriyalar yo'q.")
    else:
        await callback.message.answer("Kategoriyani tanlang:", reply_markup=_categories_keyboard(seller_id, categories))
    await callback.answer()


@router.callback_query(F.data.startswith("user_cat:"))
async def user_category_products(callback: CallbackQuery, bot: Bot) -> None:
    _, seller_id_text, category, page_text = callback.data.split(":", maxsplit=3)
    if not seller_id_text.isdigit() or not page_text.isdigit():
        await callback.answer("Noto'g'ri filter", show_alert=True)
        return

    seller_id = int(seller_id_text)
    page = max(int(page_text), 1)

    try:
        async with get_session() as session:
            products, total = await ProductService.list_products_by_seller_category(session, seller_id, category, page=page)
    except (SQLAlchemyError, RuntimeError):
        await callback.message.answer("Mahsulotlarni olishda xatolik.")
        await callback.answer()
        return

    if total == 0:
        await callback.message.answer("Bu kategoriyada mahsulot yo'q.")
        await callback.answer()
        return

    for product in products:
        if product.channel_id and product.message_id:
            try:
                await bot.copy_message(
                    chat_id=callback.message.chat.id,
                    from_chat_id=product.channel_id,
                    message_id=int(product.message_id),
                )
                continue
            except Exception:
                pass
        await callback.message.answer(f"Mahsulot ID: {product.id}")

    pages = max(ceil(total / 5), 1)
    await callback.message.answer(
        f"Kategoriya: {CATEGORIES.get(category, category)} | Jami: {total}",
        reply_markup=_pagination_keyboard("user_cat", seller_id, category, page, pages),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("user_new:"))
async def user_new_arrivals(callback: CallbackQuery, bot: Bot) -> None:
    _, seller_id_text, _, page_text = callback.data.split(":", maxsplit=3)
    if not seller_id_text.isdigit() or not page_text.isdigit():
        await callback.answer("Noto'g'ri filter", show_alert=True)
        return

    seller_id = int(seller_id_text)
    page = max(int(page_text), 1)

    try:
        async with get_session() as session:
            products, total = await ProductService.list_new_arrivals(session, seller_id, page=page)
    except (SQLAlchemyError, RuntimeError):
        await callback.answer("Xatolik", show_alert=True)
        return

    if total == 0:
        await callback.message.answer("Yangi kelgan tovarlar yo'q.")
        await callback.answer()
        return

    for product in products:
        if product.channel_id and product.message_id:
            try:
                await bot.copy_message(
                    chat_id=callback.message.chat.id,
                    from_chat_id=product.channel_id,
                    message_id=int(product.message_id),
                )
                continue
            except Exception:
                pass

    pages = max(ceil(total / 5), 1)
    await callback.message.answer(
        f"🔥 Yangi kelganlar | Jami: {total}",
        reply_markup=_pagination_keyboard("user_new", seller_id, "x", page, pages),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("user_promo:"))
async def user_promo(callback: CallbackQuery, bot: Bot) -> None:
    seller_id = int(callback.data.split(":", maxsplit=1)[1])
    await _show_seller_content(callback, bot, seller_id, "promo", "💰 Aksiya")


@router.callback_query(F.data.startswith("user_contact:"))
async def user_contact(callback: CallbackQuery, bot: Bot) -> None:
    seller_id = int(callback.data.split(":", maxsplit=1)[1])
    await _show_seller_content(callback, bot, seller_id, "contact", "📞 Aloqa")


async def _show_seller_content(
    callback: CallbackQuery,
    bot: Bot,
    seller_id: int,
    content_type: str,
    title: str,
) -> None:
    try:
        async with get_session() as session:
            content = await SellerContentService.get_content(session, seller_id=seller_id, content_type=content_type)
    except (SQLAlchemyError, RuntimeError):
        await callback.answer("Xatolik", show_alert=True)
        return

    if not content or not content.message_id:
        await callback.message.answer(f"{title} uchun ma'lumot yo'q.")
        await callback.answer()
        return

    try:
        await bot.copy_message(
            chat_id=callback.message.chat.id,
            from_chat_id=content.channel_id,
            message_id=int(content.message_id),
        )
    except Exception:
        await callback.message.answer(f"{title} uchun kontent topilmadi.")

    await callback.answer()
