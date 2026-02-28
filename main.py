import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import load_config
from db import init_db

from handlers.common import router as common_router
from handlers.client import router as client_router
from handlers.company import router as company_router


async def main():
    cfg = load_config()
    await init_db()

    bot = Bot(token=cfg.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(common_router)
    dp.include_router(client_router)
    dp.include_router(company_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
