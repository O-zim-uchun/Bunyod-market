from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_session
from app.services.product_service import CATEGORIES, ProductAccessError, ProductService
from app.services.seller_content_service import SellerContentService
from app.services.seller_service import SellerService
from app.services.user_service import UserService

router = Router(name="seller_router")


class SellerSettingsState(StatesGroup):
    waiting_promo = State()
    waiting_contact = State()


def seller_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Ombor")],
            [KeyboardButton(text="⚙️Sozlash")],
            [KeyboardButton(text="💾 Backup olish"), KeyboardButton(text="♻️ Restore qilish")],
        ],
        resize_keyboard=True,
    )


def _category_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"set_cat:{product_id}:{slug}")]
            for slug, label in CATEGORIES.items()
        ]
    )


@router.channel_post()
async def on_channel_post(message: Message, bot: Bot) -> None:
    if message.chat.type != ChatType.CHANNEL:
        return

    try:
        async with get_session() as session:
            seller = await SellerService.get_by_channel_id(session, message.chat.id)
            if seller is None:
                return

            product = await ProductService.create_or_update_from_channel(
                session=session,
                seller=seller,
                channel_id=message.chat.id,
                message_id=message.message_id,
            )
            await session.commit()

        await bot.send_message(
            seller.telegram_id,
            "Yangi mahsulot qo'shildi. Turini tanlang:",
            reply_markup=_category_keyboard(product.id),
        )
    except (SQLAlchemyError, RuntimeError):
        return


@router.edited_channel_post()
async def on_edited_channel_post(message: Message, bot: Bot) -> None:
    await on_channel_post(message, bot)


@router.callback_query(F.data.startswith("set_cat:"))
async def set_product_category(callback: CallbackQuery) -> None:
    _, product_id_text, category = callback.data.split(":", maxsplit=2)
    if not product_id_text.isdigit() or category not in CATEGORIES:
        await callback.answer("Noto'g'ri ma'lumot", show_alert=True)
        return

    try:
        async with get_session() as session:
            user = await UserService.get_or_create(session, callback.from_user.id)
            if user.role != "seller":
                await callback.answer("Faqat seller uchun", show_alert=True)
                return

            await ProductService.get_product_for_update(session, user, int(product_id_text))
            await ProductService.set_category(session, int(product_id_text), category)
            await session.commit()
    except (SQLAlchemyError, RuntimeError, ProductAccessError):
        await callback.answer("Kategoriya saqlanmadi", show_alert=True)
        return

    await callback.answer("Kategoriya saqlandi ✅", show_alert=True)


@router.message(Command("seller"))
async def seller_panel(message: Message) -> None:
    await message.answer("Seller panel", reply_markup=seller_menu_keyboard())


@router.message(F.text == "📦 Ombor")
@router.message(Command("warehouse"))
async def seller_warehouse(message: Message) -> None:
    try:
        async with get_session() as session:
            user = await UserService.get_or_create(session, message.from_user.id)
            if user.role != "seller" or not user.seller_id:
                await message.answer("Siz seller emassiz.")
                return

            count = await ProductService.seller_product_count(session, user.seller_id)
            categories = await ProductService.list_seller_categories(session, user.seller_id)
    except (SQLAlchemyError, RuntimeError):
        await message.answer("Omborni olishda xatolik.")
        return

    await message.answer(f"Ombordagi tovarlar soni: {count}")
    if not categories:
        await message.answer("Kategoriyalar topilmadi.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=CATEGORIES.get(cat, cat), callback_data=f"seller_cat:{cat}")]
            for cat in categories
        ]
    )
    await message.answer("Kategoriyani tanlang:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("seller_cat:"))
async def seller_category_products(callback: CallbackQuery) -> None:
    category = callback.data.split(":", maxsplit=1)[1]
    try:
        async with get_session() as session:
            user = await UserService.get_or_create(session, callback.from_user.id)
            if user.role != "seller" or not user.seller_id:
                await callback.answer("Ruxsat yo'q", show_alert=True)
                return

            products = await ProductService.list_seller_products_by_category(session, user.seller_id, category)
    except (SQLAlchemyError, RuntimeError):
        await callback.answer("Xatolik", show_alert=True)
        return

    if not products:
        await callback.answer("Bu kategoriyada tovar yo'q", show_alert=True)
        return

    for item in products:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👁 Preview", callback_data=f"seller_preview:{item.id}")],
                [InlineKeyboardButton(text="Tovarni o'chirish", callback_data=f"seller_delete:{item.id}")],
            ]
        )
        await callback.message.answer(f"Mahsulot ID: {item.id}", reply_markup=kb)

    await callback.answer()


@router.callback_query(F.data.startswith("seller_preview:"))
async def seller_product_preview(callback: CallbackQuery, bot: Bot) -> None:
    product_id_text = callback.data.split(":", maxsplit=1)[1]
    if not product_id_text.isdigit():
        await callback.answer("Noto'g'ri product id.", show_alert=True)
        return

    try:
        async with get_session() as session:
            user = await UserService.get_or_create(session, callback.from_user.id)
            product = await ProductService.get_product_for_update(session, user, int(product_id_text))
    except ProductAccessError:
        await callback.answer("Siz bu mahsulotni ko'ra olmaysiz.", show_alert=True)
        return
    except LookupError:
        await callback.answer("Mahsulot topilmadi.", show_alert=True)
        return
    except (SQLAlchemyError, RuntimeError):
        await callback.answer("Mahsulotni olishda xatolik.", show_alert=True)
        return

    if product.channel_id and product.message_id:
        try:
            await bot.copy_message(
                chat_id=callback.message.chat.id,
                from_chat_id=product.channel_id,
                message_id=int(product.message_id),
            )
            await callback.answer()
            return
        except Exception:
            pass

    await callback.message.answer(f"Mahsulot preview: ID {product.id}")
    await callback.answer()


@router.callback_query(F.data.startswith("seller_delete:"))
async def seller_delete_product(callback: CallbackQuery) -> None:
    product_id_text = callback.data.split(":", maxsplit=1)[1]
    if not product_id_text.isdigit():
        await callback.answer("Noto'g'ri product id.", show_alert=True)
        return

    product_id = int(product_id_text)

    try:
        async with get_session() as session:
            user = await UserService.get_or_create(session, callback.from_user.id)
            await ProductService.delete_product(session, user, product_id)
            await session.commit()
    except ProductAccessError:
        await callback.answer("Siz faqat o'zingizning mahsulotingizni o'chira olasiz.", show_alert=True)
        return
    except LookupError:
        await callback.answer("Mahsulot topilmadi.", show_alert=True)
        return
    except (SQLAlchemyError, RuntimeError):
        await callback.answer("Mahsulotni o'chirishda xatolik.", show_alert=True)
        return

    await callback.answer("Tovar o'chirildi", show_alert=True)


@router.message(F.text == "⚙️Sozlash")
async def seller_settings(message: Message) -> None:
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 Aksiya", callback_data="seller_set_promo")],
            [InlineKeyboardButton(text="📞Aloqa", callback_data="seller_set_contact")],
        ]
    )
    await message.answer("Sozlash bo'limi", reply_markup=kb)


@router.callback_query(F.data == "seller_set_promo")
async def seller_set_promo_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SellerSettingsState.waiting_promo)
    await callback.message.answer("Aksiya uchun xabar yuboring (rasm/video/matn).")
    await callback.answer()


@router.callback_query(F.data == "seller_set_contact")
async def seller_set_contact_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SellerSettingsState.waiting_contact)
    await callback.message.answer("Aloqa uchun xabar yuboring (rasm/video/matn).")
    await callback.answer()


@router.message(SellerSettingsState.waiting_promo)
async def seller_save_promo(message: Message, state: FSMContext) -> None:
    await _save_seller_content(message, "promo")
    await state.clear()


@router.message(SellerSettingsState.waiting_contact)
async def seller_save_contact(message: Message, state: FSMContext) -> None:
    await _save_seller_content(message, "contact")
    await state.clear()


async def _save_seller_content(message: Message, content_type: str) -> None:
    try:
        async with get_session() as session:
            user = await UserService.get_or_create(session, message.from_user.id)
            if user.role != "seller" or not user.seller_id:
                await message.answer("Ruxsat yo'q")
                return

            await SellerContentService.set_content(
                session=session,
                seller_id=user.seller_id,
                content_type=content_type,
                channel_id=message.chat.id,
                message_id=message.message_id,
            )
            await session.commit()
    except (SQLAlchemyError, RuntimeError):
        await message.answer("Saqlashda xatolik")
        return

    await message.answer("Saqlandi ✅")


@router.message(F.text == "💾 Backup olish")
async def seller_backup_placeholder(message: Message) -> None:
    await message.answer("💾 Backup olish eski logikasi saqlanadi.")


@router.message(F.text == "♻️ Restore qilish")
async def seller_restore_placeholder(message: Message) -> None:
    await message.answer("♻️ Restore qilish eski logikasi saqlanadi.")
