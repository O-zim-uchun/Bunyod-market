import asyncio
import logging
from os import getenv

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import Message


router = Router()


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    await message.answer("Assalomu alaykum! Bot ishga tushdi ✅")


@router.message()
async def echo_handler(message: Message) -> None:
    if message.text:
        await message.answer(message.text)


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
    dp.include_router(router)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
