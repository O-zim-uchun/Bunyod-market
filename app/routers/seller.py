from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_session
from app.services.product_service import CATEGORIES, ProductAccessError, ProductService
from app.services.seller_service import SellerService
from app.services.user_service import UserService

router = Router(name="seller_router")


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

            product = await ProductService.get_product_for_update(session, user, int(product_id_text))
            if product is None:
                await callback.answer("Mahsulot topilmadi", show_alert=True)
                return

            await ProductService.set_category(session, product.id, category)
            await session.commit()
    except (SQLAlchemyError, RuntimeError, ProductAccessError):
        await callback.answer("Kategoriya saqlanmadi", show_alert=True)
        return

    await callback.answer("Kategoriya saqlandi ✅", show_alert=True)


@router.message(Command("seller"))
async def seller_panel(message: Message) -> None:
    await message.answer("📦 Ombor: /warehouse")


@router.message(Command("warehouse"))
async def seller_warehouse(message: Message) -> None:
    try:
        async with get_session() as session:
            user = await UserService.get_or_create(session, message.from_user.id)
            if user.role != "seller" or not user.seller_id:
                await message.answer("Siz seller emassiz.")
                return

            products = await ProductService.list_products(session, user)
            count = len(products)
    except (SQLAlchemyError, RuntimeError):
        await message.answer("Omborni olishda xatolik.")
        return

    if not products:
        await message.answer("Ombordagi mahsulotlar soni: 0")
        return

    await message.answer(f"Ombordagi mahsulotlar soni: {count}")

    for item in products:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👁 Preview", callback_data=f"seller_preview:{item.id}")],
                [InlineKeyboardButton(text="❌ O'chirish", callback_data=f"seller_delete:{item.id}")],
            ]
        )
        cat = CATEGORIES.get(item.category or "", "Kategoriya tanlanmagan")
        await message.answer(f"Mahsulot ID: {item.id}\nTur: {cat}", reply_markup=kb)


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
async def seller_delete_product(callback: CallbackQuery, bot: Bot) -> None:
    product_id_text = callback.data.split(":", maxsplit=1)[1]
    if not product_id_text.isdigit():
        await callback.answer("Noto'g'ri product id.", show_alert=True)
        return

    product_id = int(product_id_text)

    try:
        async with get_session() as session:
            user = await UserService.get_or_create(session, callback.from_user.id)
            product = await ProductService.get_product_for_update(session, user, product_id)

            if product.channel_id and product.message_id:
                try:
                    await bot.delete_message(chat_id=product.channel_id, message_id=int(product.message_id))
                except Exception:
                    pass

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

    await callback.answer("Mahsulot o'chirildi", show_alert=True)
