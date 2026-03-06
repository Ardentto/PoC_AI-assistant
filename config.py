import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    openai_api_key: str
    openai_model: str


def load_config() -> Config:
    bot_token = (os.getenv("BOT_TOKEN") or "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set")

    openai_api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    openai_model = (os.getenv("OPENAI_MODEL") or "gpt-4.1-mini").strip()

    return Config(
        bot_token=bot_token,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
    )
