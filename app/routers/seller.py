from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
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
    except SQLAlchemyError:
        await message.answer("Omborni olishda xatolik.")
        return

    if not products:
        await message.answer("Ombordagi mahsulotlar soni: 0")
        return

    lines = [f"Ombordagi mahsulotlar soni: {count}"]
    for item in products:
        lines.append(f"• ID {item.id} | preview: /product_{item.id} | delete: /delete_product_{item.id}")
    await message.answer("\n".join(lines))


@router.message(lambda m: (m.text or "").startswith("/product_"))
async def seller_product_preview(message: Message, bot: Bot) -> None:
    product_id_text = (message.text or "").replace("/product_", "", 1)
    if not product_id_text.isdigit():
        await message.answer("Noto'g'ri product id.")
        return

    try:
        async with get_session() as session:
            user = await UserService.get_or_create(session, message.from_user.id)
            product = await ProductService.get_product_for_update(session, user, int(product_id_text))
    except ProductAccessError:
        await message.answer("Siz bu mahsulotni ko'ra olmaysiz.")
        return
    except LookupError:
        await message.answer("Mahsulot topilmadi.")
        return
    except SQLAlchemyError:
        await message.answer("Mahsulotni olishda xatolik.")
        return

    if product.channel_id and product.message_id:
        try:
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=product.channel_id,
                message_id=int(product.message_id),
            )
            return
        except Exception:
            pass

    await message.answer(f"Mahsulot preview: ID {product.id}")


@router.message(lambda m: (m.text or "").startswith("/delete_product_"))
async def seller_delete_product(message: Message, bot: Bot) -> None:
    product_id_text = (message.text or "").replace("/delete_product_", "", 1)
    if not product_id_text.isdigit():
        await message.answer("Noto'g'ri product id.")
        return

    product_id = int(product_id_text)

    try:
        async with get_session() as session:
            user = await UserService.get_or_create(session, message.from_user.id)
            product = await ProductService.get_product_for_update(session, user, product_id)

            if product.channel_id and product.message_id:
                try:
                    await bot.delete_message(chat_id=product.channel_id, message_id=int(product.message_id))
                except Exception:
                    pass

            await ProductService.delete_product(session, user, product_id)
            await session.commit()
    except ProductAccessError:
        await message.answer("Siz faqat o'zingizning mahsulotingizni o'chira olasiz.")
        return
    except LookupError:
        await message.answer("Mahsulot topilmadi.")
        return
    except SQLAlchemyError:
        await message.answer("Mahsulotni o'chirishda xatolik.")
        return

    await message.answer("Mahsulot o'chirildi.")
