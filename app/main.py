import asyncio
import logging
from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramConflictError

from app.db.session import init_models
from app.routers.admin import router as admin_router
from app.routers.seller import router as seller_router
from app.routers.user import router as user_router


def get_staff_bot_token() -> str:
    token = getenv("BOT_TOKEN") or getenv("TELEGRAM_BOT_TOKEN") or getenv("TOKEN")
    if not token:
        raise RuntimeError(
            "Bot token topilmadi. Railway Variables bo'limida BOT_TOKEN (yoki TELEGRAM_BOT_TOKEN) kiriting."
        )
    return token


def get_client_bot_token(staff_token: str) -> str:
    return getenv("CLIENT_BOT_TOKEN") or staff_token


def build_dispatcher(*, include_user: bool, include_staff: bool) -> Dispatcher:
    dp = Dispatcher()
    if include_user:
        dp.include_router(user_router)
    if include_staff:
        dp.include_router(seller_router)
        dp.include_router(admin_router)
    return dp


async def run_polling(bot: Bot, dp: Dispatcher, *, name: str) -> None:
    await bot.delete_webhook(drop_pending_updates=False)
    while True:
        try:
            await dp.start_polling(bot)
        except TelegramConflictError:
            logging.warning(
                "%s boti uchun TelegramConflictError: boshqa getUpdates jarayoni ishlayapti. "
                "Faqat bitta bot instance qoldiring. 15 soniyadan keyin qayta urinish."
                ,
                name,
            )
            await asyncio.sleep(15)
        except Exception:
            logging.exception("%s botida polling xatoligi, 5 soniyadan keyin qayta ishga tushadi", name)
            await asyncio.sleep(5)
        else:
            break


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await init_models()

    staff_token = get_staff_bot_token()
    client_token = get_client_bot_token(staff_token)

    if client_token == staff_token:
        bot = Bot(token=staff_token)
        dp = build_dispatcher(include_user=True, include_staff=True)
        await run_polling(bot, dp, name="universal")
        return

    staff_bot = Bot(token=staff_token)
    client_bot = Bot(token=client_token)

    staff_dp = build_dispatcher(include_user=False, include_staff=True)
    client_dp = build_dispatcher(include_user=True, include_staff=False)

    await asyncio.gather(
        run_polling(staff_bot, staff_dp, name="staff"),
        run_polling(client_bot, client_dp, name="client"),
    )


if __name__ == "__main__":
    asyncio.run(main())
