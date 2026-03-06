from aiogram import Bot
from db import list_companies
from keyboards import request_card_for_company_kb


def format_request_text(req_id: int, data: dict) -> str:
    return (
        f"📩 Новая заявка #{req_id}\n\n"
        f"Под крышей (м²): {data.get('area_under_roof_m2') or '-'}\n"
        f"Внутри стен (м²): {data.get('area_inside_walls_m2') or '-'}\n"
        f"Застеклённые (м²): {data.get('glazed_area_m2') or '-'}\n"
        f"2-й свет (м²): {data.get('second_light_m2') or '-'}\n"
        f"Тип кровли: {data.get('roof_type') or '-'}\n"
        f"Стиль кровли: {data.get('roof_style') or '-'}\n"
        f"Конструктив: {data.get('structure') or '-'}\n"
        f"Этажность: {data.get('floors') or '-'}\n"
        f"Отделка стен: {data.get('wall_finish') or '-'}\n"
        f"Фундамент: {data.get('foundation') or '-'}\n"
        f"Удалённость: {data.get('distance') or '-'}\n"
        f"Рассрочка: {data.get('installments') or '-'}\n"
        f"Септик: {data.get('septic') or '-'}\n"
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
            pass

    return sent
