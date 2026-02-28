from aiogram import Bot
from db import list_companies
from keyboards import request_card_for_company_kb


def format_request_text(req_id: int, data: dict) -> str:
    return (
        f"📩 Новая заявка #{req_id}\n\n"
        f"Что нужно: {data.get('need')}\n"
        f"Город/район: {data.get('city')}\n"
        f"Бюджет: {data.get('budget')}\n"
        f"Ограничения: {data.get('constraints')}\n"
    )


async def broadcast_request(bot: Bot, req_id: int, data: dict) -> int:
    companies = await list_companies()
    sent = 0
    text = format_request_text(req_id, data)

    for c in companies:
        try:
            await bot.send_message(
                chat_id=c["tg_id"],
                text=text,
                reply_markup=request_card_for_company_kb(req_id),
            )
            sent += 1
        except Exception:
            # в PoC просто игнорируем ошибки отправки
            pass

    return sent