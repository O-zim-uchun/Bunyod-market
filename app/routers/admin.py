from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.db.session import get_session
from app.services.seller_service import SellerService

router = Router(name="admin_router")


@router.message(Command("admin_sellers"))
async def admin_sellers(message: Message) -> None:
    async with get_session() as session:
        sellers = await SellerService.list_all_sellers(session)

    if not sellers:
        await message.answer("Sellerlar topilmadi.")
        return

    lines = [f"{seller.id}. {seller.name} (tg:{seller.telegram_id})" for seller in sellers]
    await message.answer("Barcha sellerlar:\n" + "\n".join(lines))
