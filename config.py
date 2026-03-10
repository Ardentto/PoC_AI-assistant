import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    ai_provider: str
    requesty_api_key: str
    requesty_base_url: str
    requesty_model: str
    requesty_temperature: float


def load_config() -> Config:
    bot_token = (os.getenv("BOT_TOKEN") or "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set")

    ai_provider = (os.getenv("AI_PROVIDER") or "requesty").strip().lower()

    requesty_api_key = (os.getenv("REQUESTY_API_KEY") or "").strip()
    requesty_base_url = (
        os.getenv("REQUESTY_BASE_URL") or "https://router.requesty.ai/v1"
    ).strip()
    requesty_model = (
        os.getenv("REQUESTY_MODEL") or "openai/gpt-5-nano:flex"
    ).strip()
    requesty_temperature = float(
        (os.getenv("REQUESTY_TEMPERATURE") or "0.8").strip()
    )

    if ai_provider == "requesty" and not requesty_api_key:
        raise RuntimeError("REQUESTY_API_KEY is not set")

    return Config(
        bot_token=bot_token,
        ai_provider=ai_provider,
        requesty_api_key=requesty_api_key,
        requesty_base_url=requesty_base_url,
        requesty_model=requesty_model,
        requesty_temperature=requesty_temperature,
    )
