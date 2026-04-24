from os import getenv

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.db.session import get_session
from app.services.product_service import ProductService
from app.services.seller_service import SellerService
from app.services.user_service import UserService

router = Router(name="admin_router")


class AddSellerState(StatesGroup):
    waiting_telegram_id = State()
    waiting_name = State()
    waiting_channel_id = State()


def _admin_id() -> int | None:
    value = getenv("ADMIN_ID")
    if value and value.isdigit():
        return int(value)
    return None


async def _ensure_super_admin(message: Message) -> bool:
    try:
        async with get_session() as session:
            user = await UserService.get_or_create(session, message.from_user.id, admin_id=_admin_id())
            await session.commit()
            return user.role == "super_admin"
    except Exception:
        return False


@router.message(Command("admin"))
async def admin_panel(message: Message) -> None:
    if not await _ensure_super_admin(message):
        return
    await message.answer("📊 Admin panel\n👤 Sellerlar: /admin_sellers\n➕ Seller qo'shish: /admin_add_seller\n📦 Barcha mahsulotlar: /admin_products")


@router.message(Command("admin_add_seller"))
async def admin_add_seller_start(message: Message, state: FSMContext) -> None:
    if not await _ensure_super_admin(message):
        return
    await state.set_state(AddSellerState.waiting_telegram_id)
    await message.answer("Yangi seller telegram_id sini kiriting:")


@router.message(AddSellerState.waiting_telegram_id, F.text)
async def admin_add_seller_get_tg(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Faqat raqam kiriting.")
        return

    await state.update_data(telegram_id=int(text))
    await state.set_state(AddSellerState.waiting_name)
    await message.answer("Seller nomini kiriting:")


@router.message(AddSellerState.waiting_name, F.text)
async def admin_add_seller_get_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Nom bo'sh bo'lmasin.")
        return

    await state.update_data(name=name)
    await state.set_state(AddSellerState.waiting_channel_id)
    await message.answer("Seller kanal ID sini kiriting (masalan -100123...), yoki `skip` yozing.")


@router.message(AddSellerState.waiting_channel_id, F.text)
async def admin_add_seller_get_channel(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    telegram_id = int(data["telegram_id"])
    name = data["name"]

    text = (message.text or "").strip()
    channel_id: int | None
    if text.lower() == "skip":
        channel_id = None
    elif text.lstrip("-").isdigit():
        channel_id = int(text)
    else:
        await message.answer("Kanal ID noto'g'ri. Raqam yoki `skip` yuboring.")
        return

    try:
        async with get_session() as session:
            seller = await SellerService.create_seller(
                session,
                telegram_id=telegram_id,
                name=name,
                channel_id=channel_id,
            )
            await session.commit()
        await message.answer(f"✅ Seller yaratildi: {seller.id} - {seller.name}")
    except IntegrityError:
        await message.answer("Seller ma'lumotlari noyob bo'lishi kerak (telegram_id/channel_id band bo'lishi mumkin).")
    except SQLAlchemyError:
        await message.answer("Seller yaratishda DB xatolik yuz berdi.")
    except RuntimeError as exc:
        await message.answer(str(exc))
    finally:
        await state.clear()


@router.message(Command("admin_sellers"))
async def admin_sellers(message: Message) -> None:
    if not await _ensure_super_admin(message):
        return

    try:
        async with get_session() as session:
            sellers = await SellerService.list_all_sellers(session)
    except (SQLAlchemyError, RuntimeError):
        await message.answer("Sellerlarni olishda xatolik yuz berdi.")
        return

    if not sellers:
        await message.answer("Sellerlar topilmadi.")
        return

    for seller in sellers:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ O'chirish", callback_data=f"admin_del_seller:{seller.id}")]]
        )
        await message.answer(
            f"{seller.id}. {seller.name} (tg:{seller.telegram_id})\nchannel: {seller.channel_id}",
            reply_markup=kb,
        )


@router.callback_query(F.data.startswith("admin_del_seller:"))
async def admin_delete_seller_cb(callback: CallbackQuery) -> None:
    seller_id_text = callback.data.split(":", maxsplit=1)[1]
    if not seller_id_text.isdigit():
        await callback.answer("Noto'g'ri id", show_alert=True)
        return

    try:
        async with get_session() as session:
            user = await UserService.get_or_create(session, callback.from_user.id, admin_id=_admin_id())
            if user.role != "super_admin":
                await callback.answer("Ruxsat yo'q", show_alert=True)
                return

            deleted = await SellerService.delete_seller(session, int(seller_id_text))
            await session.commit()
    except (SQLAlchemyError, RuntimeError):
        await callback.answer("Xatolik", show_alert=True)
        return

    await callback.answer("Seller o'chirildi" if deleted else "Seller topilmadi", show_alert=True)


@router.message(Command("admin_products"))
async def admin_products(message: Message) -> None:
    if not await _ensure_super_admin(message):
        return

    try:
        async with get_session() as session:
            products = await ProductService.list_all_with_seller(session)
    except (SQLAlchemyError, RuntimeError):
        await message.answer("Mahsulotlarni olishda xatolik.")
        return

    if not products:
        await message.answer("Mahsulotlar topilmadi.")
        return

    lines = []
    for product in products:
        seller_name = product.seller.name if product.seller else "NULL"
        lines.append(f"{product.id} -> seller: {seller_name} ({product.seller_id}) | category: {product.category}")

    await message.answer("📦 Barcha mahsulotlar:\n" + "\n".join(lines))
