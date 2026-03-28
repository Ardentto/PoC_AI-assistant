import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError

from config import load_config
from db import init_db

from handlers.common import router as common_router
from handlers.client import router as client_router
from handlers.company import router as company_router

from services.ai_intake import AIIntakeService
from services.voice_transcriber import VoiceTranscriber


async def build_dispatcher() -> tuple[Bot, Dispatcher]:
    cfg = load_config()
    await init_db()

    # Увеличиваем timeout для нестабильной сети до Telegram
    session = AiohttpSession(timeout=120)
    bot = Bot(token=cfg.bot_token, session=session)

    dp = Dispatcher(storage=MemoryStorage())

    dp["ai_intake"] = AIIntakeService(
        api_key=cfg.requesty_api_key,
        base_url=cfg.requesty_base_url,
        model=cfg.requesty_model,
        temperature=cfg.requesty_temperature,
    )

    # Whisper теперь lazy-loaded: модель не качается и не инициализируется на старте
    dp["voice_transcriber"] = VoiceTranscriber(
        model_size="small",
        device="cpu",
        compute_type="int8",
    )

    dp.include_router(common_router)
    dp.include_router(client_router)
    dp.include_router(company_router)

    return bot, dp


async def main():
    bot, dp = await build_dispatcher()
    await dp.start_polling(bot, skip_updates=True)


async def runner():
    while True:
        try:
            await main()
        except TelegramNetworkError as e:
            print(f"[TelegramNetworkError] {e}")
            print("Не удалось подключиться к Telegram API. Повторная попытка через 5 секунд...")
            await asyncio.sleep(5)
        except KeyboardInterrupt:
            print("Остановка бота по запросу пользователя.")
            break
        except Exception as e:
            print(f"[UnhandledError] {type(e).__name__}: {e}")
            print("Повторная попытка запуска через 5 секунд...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(runner())
