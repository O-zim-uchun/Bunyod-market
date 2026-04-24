from os import getenv

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_session
from app.services.product_service import ProductService
from app.services.seller_service import SellerService
from app.services.user_service import UserService

router = Router(name="admin_router")


class AddSellerState(StatesGroup):
    waiting_telegram_id = State()
    waiting_name = State()


def _admin_id() -> int | None:
    value = getenv("ADMIN_ID")
    if value and value.isdigit():
        return int(value)
    return None


async def _ensure_super_admin(message: Message) -> bool:
    async with get_session() as session:
        user = await UserService.get_or_create(session, message.from_user.id, admin_id=_admin_id())
        await session.commit()
        return user.role == "super_admin"


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
    data = await state.get_data()
    telegram_id = int(data["telegram_id"])
    name = (message.text or "").strip()

    if not name:
        await message.answer("Nom bo'sh bo'lmasin.")
        return

    try:
        async with get_session() as session:
            seller = await SellerService.create_seller(session, telegram_id=telegram_id, name=name)
            await session.commit()
        await message.answer(f"✅ Seller yaratildi: {seller.id} - {seller.name}")
    except SQLAlchemyError:
        await message.answer("Seller yaratishda DB xatolik yuz berdi.")
    finally:
        await state.clear()


@router.message(Command("admin_sellers"))
async def admin_sellers(message: Message) -> None:
    if not await _ensure_super_admin(message):
        return

    try:
        async with get_session() as session:
            sellers = await SellerService.list_all_sellers(session)
    except SQLAlchemyError:
        await message.answer("Sellerlarni olishda xatolik yuz berdi.")
        return

    if not sellers:
        await message.answer("Sellerlar topilmadi.")
        return

    lines = []
    for seller in sellers:
        lines.append(f"{seller.id}. {seller.name} (tg:{seller.telegram_id}) | /admin_delete_seller_{seller.id}")
    await message.answer("📋 Sellerlar:\n" + "\n".join(lines))


@router.message(F.text.startswith("/admin_delete_seller_"))
async def admin_delete_seller(message: Message) -> None:
    if not await _ensure_super_admin(message):
        return

    seller_id_text = (message.text or "").replace("/admin_delete_seller_", "", 1)
    if not seller_id_text.isdigit():
        await message.answer("Noto'g'ri seller id")
        return

    try:
        async with get_session() as session:
            deleted = await SellerService.delete_seller(session, int(seller_id_text))
            await session.commit()
    except SQLAlchemyError:
        await message.answer("Sellerni o'chirishda xatolik.")
        return

    if not deleted:
        await message.answer("Seller topilmadi.")
    else:
        await message.answer("Seller o'chirildi.")


@router.message(Command("admin_products"))
async def admin_products(message: Message) -> None:
    if not await _ensure_super_admin(message):
        return

    try:
        async with get_session() as session:
            products = await ProductService.list_all_with_seller(session)
    except SQLAlchemyError:
        await message.answer("Mahsulotlarni olishda xatolik.")
        return

    if not products:
        await message.answer("Mahsulotlar topilmadi.")
        return

    lines = []
    for product in products:
        seller_name = product.seller.name if product.seller else "NULL"
        lines.append(f"{product.id} -> seller: {seller_name} ({product.seller_id})")

    await message.answer("📦 Barcha mahsulotlar:\n" + "\n".join(lines))
