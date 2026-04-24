import asyncio
import logging
from os import getenv

from aiogram import Bot, Dispatcher

from app.routers.admin import router as admin_router
from app.routers.seller import router as seller_router
from app.routers.user import router as user_router


def get_bot_token() -> str:
    token = getenv("BOT_TOKEN") or getenv("TELEGRAM_BOT_TOKEN") or getenv("TOKEN")
    if not token:
        raise RuntimeError(
            "Bot token topilmadi. Railway Variables bo'limida BOT_TOKEN (yoki TELEGRAM_BOT_TOKEN) kiriting."
        )
    return token


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=get_bot_token())
    dp = Dispatcher()

    dp.include_router(admin_router)
    dp.include_router(seller_router)
    dp.include_router(user_router)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
