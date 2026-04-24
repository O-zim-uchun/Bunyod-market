from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_session
from app.services.product_service import ProductAccessError, ProductService
from app.services.user_service import UserService

router = Router(name="seller_router")


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
        await message.answer(f"Mahsulot ID: {item.id}", reply_markup=kb)


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
