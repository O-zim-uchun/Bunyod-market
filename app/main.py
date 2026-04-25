import asyncio
import logging
from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramConflictError

from app.db.session import init_models
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

    await init_models()

    bot = Bot(token=get_bot_token())
    dp = Dispatcher()

    dp.include_router(user_router)
    dp.include_router(seller_router)
    dp.include_router(admin_router)

    # Polling only: disable webhook explicitly
    await bot.delete_webhook(drop_pending_updates=False)

    while True:
        try:
            await dp.start_polling(bot)
        except TelegramConflictError:
            logging.warning(
                "TelegramConflictError: boshqa getUpdates jarayoni ishlayapti. "
                "Faqat bitta bot instance qoldiring. 15 soniyadan keyin qayta urinish."
            )
            await asyncio.sleep(15)
        except Exception:
            logging.exception("Polling xatoligi, 5 soniyadan keyin qayta ishga tushadi")
            await asyncio.sleep(5)
        else:
            break


if __name__ == "__main__":
    asyncio.run(main())
