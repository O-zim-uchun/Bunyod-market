import random
from math import ceil
from os import getenv

from aiogram import Bot, F, Router
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_session
from app.models.seller import Seller
from app.models.user import User
from app.services.favorite_service import FavoriteService
from app.services.product_service import CATEGORIES, ProductService
from app.services.seller_content_service import SellerContentService
from app.services.seller_service import SellerService
from app.services.user_service import UserService

router = Router(name="user_router")


WELCOME_TEXT = "Siz bu bot o'rqali uyingizdan chiqmasdan va istagan vaqtda qidirgan barcha narsangizni topasiz!\n/start bosing"


def _admin_id() -> int | None:
    value = getenv("ADMIN_ID")
    if value and value.isdigit():
        return int(value)
    return None


def _is_public_user_entry_event(event: Message | CallbackQuery) -> bool:
    if isinstance(event, Message):
        text = (event.text or "").strip()
        return text.startswith("/start") or text.startswith("/satr")
    return False


class UserRoleMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if _is_public_user_entry_event(event):
            return await handler(event, data)

        telegram_user = getattr(event, "from_user", None)
        if telegram_user is None:
            return await handler(event, data)

        try:
            async with get_session() as session:
                user = await UserService.get_or_create(session, telegram_user.id, admin_id=_admin_id())
                await session.commit()
        except Exception:
            if isinstance(event, CallbackQuery):
                await event.answer("Role tekshirishda xatolik.", show_alert=True)
                return None
            if isinstance(event, Message):
                await event.answer("Role tekshirishda xatolik.")
                return None
            return None

        if user.role != "user":
            if isinstance(event, CallbackQuery):
                await event.answer("Bu bo'lim faqat mijozlar uchun.", show_alert=True)
                return None
            if isinstance(event, Message):
                await event.answer("Bu bo'lim faqat mijozlar uchun. /start bosing.")
                return None
            return None

        return await handler(event, data)


router.message.middleware(UserRoleMiddleware())
router.callback_query.middleware(UserRoleMiddleware())


def _remove_clicked_button(markup: InlineKeyboardMarkup | None, clicked_data: str) -> InlineKeyboardMarkup | None:
    if markup is None:
        return None
    new_rows = []
    for row in markup.inline_keyboard:
        kept = [btn for btn in row if getattr(btn, "callback_data", None) != clicked_data]
        if kept:
            new_rows.append(kept)
    return InlineKeyboardMarkup(inline_keyboard=new_rows) if new_rows else None


def _static_buttons_row(seller_id: int) -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(text="⚖️Katta bozor", callback_data="market:1"),
        InlineKeyboardButton(text="⚡️TezGo", callback_data="tezgo:1"),
        InlineKeyboardButton(text="⬅️ Ortga", callback_data=f"back:seller:{seller_id}"),
    ]


def _seller_sections_keyboard(seller_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛍 Tovarlar", callback_data=f"user_shop:{seller_id}")],
            [InlineKeyboardButton(text="🔥 Yangi kelganlar", callback_data=f"user_new:{seller_id}:1")],
            [InlineKeyboardButton(text="💰 Aksiya", callback_data=f"user_promo:{seller_id}")],
            [InlineKeyboardButton(text="📞 Aloqa", callback_data=f"user_contact:{seller_id}")],
            [InlineKeyboardButton(text="❤️ Sevimlilar", callback_data=f"user_favs:{seller_id}")],
            _static_buttons_row(seller_id),
        ]
    )


def _categories_keyboard(seller_id: int, categories: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=CATEGORIES.get(slug, slug), callback_data=f"user_cat:{seller_id}:{slug}:1")]
        for slug in categories
    ]
    rows.append(_static_buttons_row(seller_id))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _pagination_keyboard(prefix: str, seller_id: int, key: str, page: int, pages: int) -> InlineKeyboardMarkup:
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"{prefix}:{seller_id}:{key}:{page - 1}"))
    buttons.append(InlineKeyboardButton(text=f"{page}/{pages}", callback_data="noop"))
    if page < pages:
        buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"{prefix}:{seller_id}:{key}:{page + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons, _static_buttons_row(seller_id)])


@router.message(Command("satr"))
async def satr_hint(message: Message) -> None:
    await message.answer(WELCOME_TEXT)


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery) -> None:
    await callback.answer()


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
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

    ids = [s.id for s in sellers]
    random.shuffle(ids)
    await state.update_data(seller_order=ids)
    await message.answer("🛍 Mijoz paneli")
    await _show_sellers_page(message, state, page=1)


async def _show_sellers_page(target, state: FSMContext, page: int) -> None:
    data = await state.get_data()
    seller_order: list[int] = data.get("seller_order", [])
    if not seller_order:
        if isinstance(target, Message):
            await target.answer("Do'konlar topilmadi.")
        else:
            await target.message.answer("Do'konlar topilmadi.")
        return

    page_size = 6
    pages = max(ceil(len(seller_order) / page_size), 1)
    page = max(1, min(page, pages))
    start = (page - 1) * page_size
    page_ids = seller_order[start : start + page_size]

    async with get_session() as session:
        sellers = await session.execute(select(Seller).where(Seller.id.in_(page_ids)))
        mapping = {s.id: s for s in sellers.scalars().all()}

    rows = []
    for sid in page_ids:
        seller = mapping.get(sid)
        if seller:
            rows.append([InlineKeyboardButton(text=seller.name, callback_data=f"seller_select:{seller.id}")])

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"shop_page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page}/{pages}", callback_data="noop"))
    if page < pages:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"shop_page:{page + 1}"))
    rows.append(nav)

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    text = "Do'konni tanlang:"
    if isinstance(target, Message):
        await target.answer(text, reply_markup=kb)
    else:
        await target.message.edit_reply_markup(reply_markup=kb)
        await target.answer()


@router.callback_query(F.data.startswith("shop_page:"))
async def shops_page(callback: CallbackQuery, state: FSMContext) -> None:
    page = int(callback.data.split(":", maxsplit=1)[1])
    await _show_sellers_page(callback, state, page)


@router.callback_query(F.data.startswith("seller_select:"))
async def seller_select(callback: CallbackQuery) -> None:
    seller_id = int(callback.data.split(":", maxsplit=1)[1])
    async with get_session() as session:
        seller = await session.get(Seller, seller_id)

    if not seller:
        await callback.answer("Do'kon topilmadi", show_alert=True)
        return

    info = f"🏪 {seller.name}\nID: {seller.id}\nKanal: {seller.channel_id or '—'}"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Do'kon haqida", callback_data=f"about:{seller_id}")]]
    )
    await callback.message.answer(info, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("about:"))
async def about_store(callback: CallbackQuery) -> None:
    seller_id = int(callback.data.split(":", maxsplit=1)[1])
    new_markup = _remove_clicked_button(callback.message.reply_markup, callback.data)
    try:
        await callback.message.edit_reply_markup(reply_markup=new_markup)
    except Exception:
        pass
    await callback.message.answer("Do'kon paneli:", reply_markup=_seller_sections_keyboard(seller_id))
    await callback.answer()


@router.callback_query(F.data.startswith("back:seller:"))
async def back_to_store(callback: CallbackQuery) -> None:
    seller_id = int(callback.data.split(":", maxsplit=2)[2])
    await callback.message.answer("Do'kon paneli:", reply_markup=_seller_sections_keyboard(seller_id))
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

    new_markup = _remove_clicked_button(callback.message.reply_markup, callback.data)
    try:
        await callback.message.edit_reply_markup(reply_markup=new_markup)
    except Exception:
        pass
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
            user = await UserService.get_or_create(session, callback.from_user.id, admin_id=_admin_id())
            await session.commit()
    except (SQLAlchemyError, RuntimeError):
        await callback.message.answer("Mahsulotlarni olishda xatolik.")
        await callback.answer()
        return

    if total == 0:
        await callback.message.answer("Bu kategoriyada mahsulot yo'q.")
        await callback.answer()
        return

    for product in products:
        action_kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❤️ Sevimli", callback_data=f"fav:{seller_id}:{product.id}")]]
        )
        if product.channel_id and product.message_id:
            try:
                await bot.copy_message(
                    chat_id=callback.message.chat.id,
                    from_chat_id=product.channel_id,
                    message_id=int(product.message_id),
                    reply_markup=action_kb,
                )
                continue
            except Exception:
                pass
        await callback.message.answer(f"Mahsulot ID: {product.id}", reply_markup=action_kb)

    pages = max(ceil(total / 5), 1)
    await callback.message.answer(
        f"Kategoriya: {CATEGORIES.get(category, category)} | Jami: {total}",
        reply_markup=_pagination_keyboard("user_cat", seller_id, category, page, pages),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("fav:"))
async def toggle_favorite(callback: CallbackQuery) -> None:
    _, seller_id_text, product_id_text = callback.data.split(":", maxsplit=2)
    if not seller_id_text.isdigit() or not product_id_text.isdigit():
        await callback.answer("Xatolik", show_alert=True)
        return

    try:
        async with get_session() as session:
            user = await UserService.get_or_create(session, callback.from_user.id, admin_id=_admin_id())
            added = await FavoriteService.toggle(
                session,
                user_id=user.id,
                seller_id=int(seller_id_text),
                product_id=int(product_id_text),
            )
            await session.commit()
    except (SQLAlchemyError, RuntimeError):
        await callback.answer("Xatolik", show_alert=True)
        return

    await callback.answer("Sevimlilarga qo'shildi ❤️" if added else "Sevimlilardan olindi")


@router.callback_query(F.data.startswith("user_favs:"))
async def user_favs(callback: CallbackQuery, bot: Bot) -> None:
    seller_id = int(callback.data.split(":", maxsplit=1)[1])
    try:
        async with get_session() as session:
            user = await UserService.get_or_create(session, callback.from_user.id, admin_id=_admin_id())
            products = await FavoriteService.list_by_seller(session, user_id=user.id, seller_id=seller_id)
            await session.commit()
    except (SQLAlchemyError, RuntimeError):
        await callback.answer("Xatolik", show_alert=True)
        return

    if not products:
        await callback.message.answer("Sevimlilar bo'sh.")
    else:
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

    new_markup = _remove_clicked_button(callback.message.reply_markup, callback.data)
    try:
        await callback.message.edit_reply_markup(reply_markup=new_markup)
    except Exception:
        pass
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


@router.callback_query(F.data == "market:1")
async def show_big_market(callback: CallbackQuery, bot: Bot) -> None:
    try:
        async with get_session() as session:
            admin_user_row = await session.execute(select(User).where(User.role == "super_admin").limit(1))
            admin_user = admin_user_row.scalar_one_or_none()
            if not admin_user or not admin_user.seller_id:
                await callback.message.answer("⚖️Katta bozor hali bo'sh.")
                await callback.answer()
                return
            products = await ProductService.list_products_by_seller(session, admin_user.seller_id)
    except (SQLAlchemyError, RuntimeError):
        await callback.answer("Xatolik", show_alert=True)
        return

    if not products:
        await callback.message.answer("⚖️Katta bozor hali bo'sh.")
    else:
        for product in products[:10]:
            if product.channel_id and product.message_id:
                try:
                    await bot.copy_message(callback.message.chat.id, product.channel_id, int(product.message_id))
                except Exception:
                    pass
    await callback.answer()


@router.callback_query(F.data == "tezgo:1")
async def show_tezgo(callback: CallbackQuery, bot: Bot) -> None:
    try:
        async with get_session() as session:
            admin_user_row = await session.execute(select(User).where(User.role == "super_admin").limit(1))
            admin_user = admin_user_row.scalar_one_or_none()
            if not admin_user or not admin_user.seller_id:
                await callback.message.answer("⚡️TezGo hozircha sozlanmagan.")
                await callback.answer()
                return
            content = await SellerContentService.get_content(session, admin_user.seller_id, "tezgo")
    except (SQLAlchemyError, RuntimeError):
        await callback.answer("Xatolik", show_alert=True)
        return

    if not content:
        await callback.message.answer("⚡️TezGo hozircha sozlanmagan.")
    else:
        try:
            await bot.copy_message(callback.message.chat.id, content.channel_id, int(content.message_id))
        except Exception:
            await callback.message.answer("⚡️TezGo kontenti topilmadi.")

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

    new_markup = _remove_clicked_button(callback.message.reply_markup, callback.data)
    try:
        await callback.message.edit_reply_markup(reply_markup=new_markup)
    except Exception:
        pass
    await callback.answer()
