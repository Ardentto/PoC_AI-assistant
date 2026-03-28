from typing import Dict, List, Optional

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from db import (
    set_user_role,
    create_request,
    list_requests_by_client,
    get_request,
    list_offers,
)
from keyboards import client_menu_kb, confirm_kb, request_open_kb, back_to_menu_kb
from states import ClientLeadFlow
from services.broadcast import broadcast_request
from services.ai_intake import AIIntakeService
from services.intake_extractor import (
    HUMAN_QUESTIONS,
    FIELD_EXPLANATIONS,
    extract_known,
    compute_pending,
    is_filled,
)
from services.budget_advisor import format_budget_hint, format_field_budget_hint

router = Router()


async def safe_answer_callback(c: CallbackQuery):
    try:
        await c.answer()
    except TelegramBadRequest:
        pass


def user_needs_explanation(text: str) -> bool:
    t = (text or "").lower()
    triggers = [
        "не понимаю",
        "не понял",
        "не поняла",
        "что это",
        "что это значит",
        "что значит",
        "объясни",
        "объясните",
        "можно проще",
        "не знаю что выбрать",
    ]
    return any(x in t for x in triggers)


def get_field_explanation(field: str) -> str:
    explanation = FIELD_EXPLANATIONS.get(field)
    question = HUMAN_QUESTIONS.get(field, "")
    if explanation:
        return f"{explanation}\n\nЕсли говорить проще: {question}"
    return f"Хорошо, объясню проще.\n\n{question}"


def format_house_summary(d: Dict[str, str]) -> str:
    return (
        "🧾 Черновик заявки:\n\n"
        f"Клиент: {d.get('client_name') or '-'}\n"
        f"Локация: {d.get('lead_location') or '-'}\n"
        f"Участок: {d.get('has_land') or '-'}\n"
        f"Старт строительства: {d.get('start_timeline') or '-'}\n"
        f"Контакт: {d.get('lead_contact') or '-'}\n\n"
        f"Цель покупки: {d.get('purchase_goal') or '-'}\n"
        f"Бюджет: {d.get('budget') or '-'}\n"
        f"Под крышей (м²): {d.get('area_under_roof_m2') or '-'}\n"
        f"Полезная площадь (м²): {d.get('area_inside_walls_m2') or '-'}\n"
        f"Спальни: {d.get('bedrooms') or '-'}\n"
        f"Остекление (м²): {d.get('glazed_area_m2') or '-'}\n"
        f"2-й свет (м²): {d.get('second_light_m2') or '-'}\n"
        f"Тип кровли: {d.get('roof_type') or '-'}\n"
        f"Стиль кровли: {d.get('roof_style') or '-'}\n"
        f"Конструктив: {d.get('structure') or '-'}\n"
        f"Этажность: {d.get('floors') or '-'}\n"
        f"Отделка стен: {d.get('wall_finish') or '-'}\n"
        f"Фундамент: {d.get('foundation') or '-'}\n"
        f"Удалённость: {d.get('distance') or '-'}\n"
        f"Рассрочка: {d.get('installments') or '-'}\n"
        f"Септик: {d.get('septic') or '-'}\n"
    )


def request_title(d: Dict[str, str]) -> str:
    parts = []
    if d.get("lead_location"):
        parts.append(d["lead_location"])
    if d.get("budget"):
        parts.append(d["budget"])
    if d.get("area_under_roof_m2"):
        parts.append(d["area_under_roof_m2"])
    return "Дом • " + (" • ".join(parts) if parts else "заявка")


async def ask_next_question(m: Message, state: FSMContext) -> None:
    data = await state.get_data()
    collected: Dict[str, str] = dict(data.get("collected") or {})
    pending: List[str] = list(data.get("pending") or [])

    if not pending:
        pending = compute_pending(collected)

    if not pending:
        summary = format_house_summary(collected) + "\nПодтверждаем отправку компаниям?"
        await m.answer(summary, reply_markup=confirm_kb())
        await state.set_state(ClientLeadFlow.confirm)
        await state.update_data(current_field=None, pending=[])
        return

    field = pending[0]
    await state.update_data(current_field=field, pending=pending)

    # Вопрос + короткая подсказка под бюджет, если она уместна
    question = HUMAN_QUESTIONS[field]
    await m.answer(question)

    budget_hint = format_field_budget_hint(field, collected.get("budget", ""))
    if budget_hint:
        await m.answer(budget_hint)


@router.callback_query(F.data == "role:client")
async def set_role_client(c: CallbackQuery):
    await safe_answer_callback(c)
    await set_user_role(c.from_user.id, "client")
    await c.message.answer("Ок, вы клиент. Откроем меню:", reply_markup=client_menu_kb())


@router.callback_query(F.data == "client:new")
async def new_request(c: CallbackQuery, state: FSMContext):
    await safe_answer_callback(c)
    await state.clear()
    await c.message.answer(
        "Давайте быстро оформим заявку. Сначала 5 коротких вопросов.\n\n"
        "Как к вам обращаться?"
    )
    await state.set_state(ClientLeadFlow.lead_name)


@router.message(ClientLeadFlow.lead_name)
async def lead_name(m: Message, state: FSMContext):
    collected = {"client_name": (m.text or "").strip()}
    await state.update_data(collected=collected)
    await m.answer("В каком районе или городе планируете строить дом?")
    await state.set_state(ClientLeadFlow.lead_location)


@router.message(ClientLeadFlow.lead_location)
async def lead_location(m: Message, state: FSMContext):
    data = await state.get_data()
    collected = dict(data.get("collected") or {})
    collected["lead_location"] = (m.text or "").strip()
    await state.update_data(collected=collected)
    await m.answer("У вас уже есть участок? Можно ответить: да / нет / в процессе.")
    await state.set_state(ClientLeadFlow.lead_has_land)


@router.message(ClientLeadFlow.lead_has_land)
async def lead_has_land(m: Message, state: FSMContext):
    data = await state.get_data()
    collected = dict(data.get("collected") or {})
    collected["has_land"] = (m.text or "").strip()
    await state.update_data(collected=collected)
    await m.answer("Когда вам было бы удобно начать строительство?")
    await state.set_state(ClientLeadFlow.lead_timeline)


@router.message(ClientLeadFlow.lead_timeline)
async def lead_timeline(m: Message, state: FSMContext):
    data = await state.get_data()
    collected = dict(data.get("collected") or {})
    collected["start_timeline"] = (m.text or "").strip()
    await state.update_data(collected=collected)
    await m.answer("Какой способ связи удобнее кроме Telegram?")
    await state.set_state(ClientLeadFlow.lead_contact)


@router.message(ClientLeadFlow.lead_contact)
async def lead_contact(m: Message, state: FSMContext):
    data = await state.get_data()
    collected = dict(data.get("collected") or {})
    collected["lead_contact"] = (m.text or "").strip()
    await state.update_data(collected=collected)

    await m.answer(
        "Отлично.\n\n"
        "Теперь отправьте голосовое сообщение и в свободной форме расскажите:\n"
        "— какой дом вы хотите\n"
        "— какой у вас бюджет\n"
        "— для каких целей покупаете\n\n"
        "Можно рассказывать простыми словами."
    )
    await state.set_state(ClientLeadFlow.wait_voice)


@router.message(ClientLeadFlow.wait_voice, F.voice)
async def lead_voice(m: Message, state: FSMContext, voice_transcriber):
    data = await state.get_data()
    collected: Dict[str, str] = dict(data.get("collected") or {})

    transcript = await voice_transcriber.download_and_transcribe(m.bot, m.voice)
    transcript = (transcript or "").strip()

    if not transcript or len(transcript) < 8:
        await m.answer(
            "Я почти не смог разобрать голосовое сообщение.\n\n"
            "Попробуйте отправить его ещё раз, желательно чуть громче и подробнее.\n"
            "Если удобнее, можете просто написать это текстом."
        )
        return

    await state.update_data(transcript=transcript)

    combined_text = "\n".join(
        [
            collected.get("client_name", ""),
            collected.get("lead_location", ""),
            collected.get("has_land", ""),
            collected.get("start_timeline", ""),
            collected.get("lead_contact", ""),
            transcript,
        ]
    ).strip()

    extracted = extract_known(combined_text)
    collected.update(extracted)

    await state.update_data(
        collected=collected,
        full_context=combined_text,
        transcript=transcript,
    )

    understood_parts = []
    if collected.get("purchase_goal"):
        understood_parts.append(f"цель: {collected['purchase_goal']}")
    if collected.get("budget"):
        understood_parts.append(f"бюджет: {collected['budget']}")
    if collected.get("area_under_roof_m2"):
        understood_parts.append(f"размер дома: {collected['area_under_roof_m2']}")
    if collected.get("floors"):
        understood_parts.append(f"этажность: {collected['floors']}")
    if collected.get("structure"):
        understood_parts.append(f"материал: {collected['structure']}")
    if collected.get("bedrooms"):
        understood_parts.append(f"спален: {collected['bedrooms']}")

    if understood_parts:
        await m.answer(
            "Спасибо, я понял из голосового следующее:\n"
            + "\n".join(f"— {x}" for x in understood_parts)
        )
    else:
        await m.answer(
            "Спасибо, голосовое получил, но деталей из него вытащилось мало.\n"
            "Сейчас задам несколько коротких уточняющих вопросов."
        )

    budget_hint = format_budget_hint(collected.get("budget", ""))
    if budget_hint:
        await m.answer(budget_hint)

    pending = compute_pending(collected)
    await state.update_data(pending=pending, current_field=None)

    if not pending:
        summary = format_house_summary(collected) + "\nПодтверждаем отправку компаниям?"
        await m.answer(summary, reply_markup=confirm_kb())
        await state.set_state(ClientLeadFlow.confirm)
        return

    await state.set_state(ClientLeadFlow.clarify)
    await ask_next_question(m, state)


@router.message(ClientLeadFlow.wait_voice, F.text)
async def lead_wait_voice_text(m: Message, state: FSMContext):
    data = await state.get_data()
    collected: Dict[str, str] = dict(data.get("collected") or {})

    text = (m.text or "").strip()
    if len(text) < 8:
        await m.answer(
            "Сообщение получилось слишком коротким.\n"
            "Опишите, пожалуйста, чуть подробнее: какой дом хотите, какой бюджет и для каких целей покупаете."
        )
        return

    combined_text = "\n".join(
        [
            collected.get("client_name", ""),
            collected.get("lead_location", ""),
            collected.get("has_land", ""),
            collected.get("start_timeline", ""),
            collected.get("lead_contact", ""),
            text,
        ]
    ).strip()

    extracted = extract_known(combined_text)
    collected.update(extracted)

    await state.update_data(
        collected=collected,
        full_context=combined_text,
        transcript=text,
    )

    await m.answer("Спасибо, я учёл ваше текстовое описание.")

    budget_hint = format_budget_hint(collected.get("budget", ""))
    if budget_hint:
        await m.answer(budget_hint)

    pending = compute_pending(collected)
    await state.update_data(pending=pending, current_field=None)

    if not pending:
        summary = format_house_summary(collected) + "\nПодтверждаем отправку компаниям?"
        await m.answer(summary, reply_markup=confirm_kb())
        await state.set_state(ClientLeadFlow.confirm)
        return

    await state.set_state(ClientLeadFlow.clarify)
    await ask_next_question(m, state)


@router.message(ClientLeadFlow.wait_voice)
async def lead_wait_voice_wrong_type(m: Message):
    await m.answer(
        "Пожалуйста, отправьте голосовое сообщение.\n"
        "Если удобнее, можно вместо этого написать всё текстом."
    )


@router.message(ClientLeadFlow.clarify)
async def house_clarify(m: Message, state: FSMContext, ai_intake: AIIntakeService):
    data = await state.get_data()
    collected: Dict[str, str] = dict(data.get("collected") or {})
    pending: List[str] = list(data.get("pending") or [])
    current_field: Optional[str] = data.get("current_field")
    full_context = data.get("full_context") or ""

    if not current_field:
        await ask_next_question(m, state)
        return

    user_text = (m.text or "").strip()

    if user_needs_explanation(user_text):
        await m.answer(get_field_explanation(current_field))
        budget_hint = format_field_budget_hint(current_field, collected.get("budget", ""))
        if budget_hint:
            await m.answer(budget_hint)
        return

    # Сначала пробуем вытянуть данные правилами
    extracted = extract_known(user_text)
    collected.update(extracted)
    await state.update_data(collected=collected)

    if is_filled(collected, current_field):
        if pending and pending[0] == current_field:
            pending = pending[1:]
        else:
            pending = compute_pending(collected)

        await state.update_data(pending=pending, current_field=None)
        await ask_next_question(m, state)
        return

    # Потом AI решает, можно ли считать ответ достаточным
    eval_ = await ai_intake.evaluate(
        field_key=current_field,
        field_question=HUMAN_QUESTIONS[current_field],
        user_answer=user_text,
        collected=collected,
    )

    if eval_.need_clarify:
        await m.answer(
            eval_.clarify_question
            or ("Уточню чуть проще: " + HUMAN_QUESTIONS[current_field])
        )
        budget_hint = format_field_budget_hint(current_field, collected.get("budget", ""))
        if budget_hint:
            await m.answer(budget_hint)
        return

    if eval_.is_answered:
        if eval_.value and eval_.value.strip():
            collected[current_field] = eval_.value.strip()
        else:
            collected[current_field] = user_text

        full_context = (full_context + "\n" + user_text).strip()

        if pending and pending[0] == current_field:
            pending = pending[1:]
        else:
            pending = compute_pending(collected)

        await state.update_data(
            collected=collected,
            full_context=full_context,
            pending=pending,
            current_field=None,
        )
        await ask_next_question(m, state)
        return

    await m.answer("Не до конца понял ответ. Давайте проще: " + HUMAN_QUESTIONS[current_field])
    budget_hint = format_field_budget_hint(current_field, collected.get("budget", ""))
    if budget_hint:
        await m.answer(budget_hint)


@router.callback_query(F.data == "client:confirm_edit")
async def confirm_edit(c: CallbackQuery, state: FSMContext):
    await safe_answer_callback(c)
    await state.clear()
    await c.message.answer("Ок, начнём заново.\n\nКак к вам обращаться?")
    await state.set_state(ClientLeadFlow.lead_name)


@router.callback_query(F.data == "client:confirm_cancel")
async def confirm_cancel(c: CallbackQuery, state: FSMContext):
    await safe_answer_callback(c)
    await state.clear()
    await c.message.answer("Отменено. Меню клиента:", reply_markup=client_menu_kb())


@router.callback_query(F.data == "client:confirm_yes")
async def confirm_yes(c: CallbackQuery, state: FSMContext):
    await safe_answer_callback(c)
    st = await state.get_data()
    collected: Dict[str, str] = dict(st.get("collected") or {})

    req_id = await create_request(c.from_user.id, collected)
    sent = await broadcast_request(c.bot, req_id, collected)

    await state.clear()
    await c.message.answer(
        f"✅ Заявка #{req_id} создана и разослана компаниям: {sent} шт.\n"
        "Как только будут отклики — я пришлю сообщение.",
        reply_markup=client_menu_kb(),
    )


@router.callback_query(F.data == "client:list")
async def my_requests(c: CallbackQuery):
    await safe_answer_callback(c)
    items = await list_requests_by_client(c.from_user.id)
    if not items:
        await c.message.answer("У вас пока нет заявок.", reply_markup=client_menu_kb())
        return

    await c.message.answer("📋 Ваши заявки:")
    for r in items[:10]:
        d = r["data"] or {}
        title = request_title(d)
        await c.message.answer(
            f"#{r['id']} • {title} • {r['status']}",
            reply_markup=request_open_kb(r["id"]),
        )


@router.callback_query(F.data.startswith("client:open:"))
async def open_request(c: CallbackQuery):
    await safe_answer_callback(c)
    req_id = int(c.data.split(":")[-1])
    req = await get_request(req_id)
    if not req or req["client_tg_id"] != c.from_user.id:
        await c.message.answer("Не нашёл эту заявку.")
        return

    data = req["data"] or {}
    offers = await list_offers(req_id)

    text = f"🧾 Заявка #{req_id}\n\n" + format_house_summary(data) + "\n"

    if not offers:
        text += "⏳ Откликов пока нет."
    else:
        text += "📨 Отклики:\n"
        for o in offers[:20]:
            text += (
                f"\n— {o['company_name']}\n"
                f"  Контакт: {o['company_contact']}\n"
                f"  Стоимость: {o['price']}\n"
                f"  Комментарий: {o['comment'] or '-'}\n"
            )

    await c.message.answer(text, reply_markup=back_to_menu_kb())
