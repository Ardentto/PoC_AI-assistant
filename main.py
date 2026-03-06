import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import load_config
from db import init_db

from handlers.common import router as common_router
from handlers.client import router as client_router
from handlers.company import router as company_router

from services.ai_intake import AIIntakeService


async def main():
    cfg = load_config()
    await init_db()

    bot = Bot(token=cfg.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    # Dependency Injection: будет доступно в хендлерах как параметр ai_intake
    dp["ai_intake"] = AIIntakeService(
        api_key=cfg.openai_api_key, model=cfg.openai_model
    )

    dp.include_router(common_router)
    dp.include_router(client_router)
    dp.include_router(company_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
