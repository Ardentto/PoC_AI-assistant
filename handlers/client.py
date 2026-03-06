import re
from typing import Dict, List, Optional

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from db import (
    set_user_role,
    create_request,
    list_requests_by_client,
    get_request,
    list_offers,
)
from keyboards import (
    client_menu_kb,
    confirm_kb,
    request_open_kb,
    back_to_menu_kb,
)
from states import ClientHouseIntake
from services.broadcast import broadcast_request
from services.ai_intake import AIIntakeService

router = Router()

# Порядок важен: так анкета будет идти последовательно
FIELDS: Dict[str, str] = {
    "area_under_roof_m2": "Сколько м² под крышей (общая площадь)?",
    "area_inside_walls_m2": "Сколько м² внутри стен (полезная/жилая площадь)?",
    "glazed_area_m2": "Какая площадь застеклённых проёмов (м²) примерно?",
    "second_light_m2": "Нужен ли 2-й свет? Если да — сколько м²?",
    "roof_type": "Тип кровли: двускатная/вальмовая/плоская/односкатная/другое?",
    "roof_style": "Стиль кровли/внешний вид (современный, классика и т.п.)?",
    "structure": "Конструктив: каркас, газобетон, кирпич, брус, монолит и т.д.?",
    "floors": "Этажность: 1 / 1.5 / 2 / 3?",
    "wall_finish": "Отделка стен (фасад): штукатурка/кирпич/сайдинг/планкен/другое?",
    "foundation": "Фундамент: плита/лента/сваи/ростверк/другое?",
    "distance": "Удалённость/локация: где строить и насколько далеко от города?",
    "installments": "Нужна рассрочка? (да/нет/условия)",
    "septic": "Септик нужен? (да/нет/тип/производительность если знаете)",
}

NUM_RE = r"(\d+(?:[.,]\d+)?)"


# --- Мини-парсер (быстрый prefill, экономит запросы к AI) ---
def _normalize(text: str) -> str:
    return " ".join((text or "").split())


def _find_m2(text: str, keywords: List[str]) -> str | None:
    kw = "|".join(map(re.escape, keywords))
    p1 = rf"({kw}).{{0,25}}{NUM_RE}\s*(?:м2|м²|кв\.?\s*м|кв|квадрат)"
    m = re.search(p1, text, re.IGNORECASE)
    if m:
        return m.group(2).replace(",", ".")
    p2 = rf"{NUM_RE}\s*(?:м2|м²|кв\.?\s*м|кв|квадрат).{{0,25}}({kw})"
    m2 = re.search(p2, text, re.IGNORECASE)
    if m2:
        return m2.group(1).replace(",", ".")
    return None


def _pick_one(text: str, options: Dict[str, List[str]]) -> str | None:
    for label, keys in options.items():
        for k in keys:
            if re.search(rf"\b{re.escape(k)}\b", text, re.IGNORECASE):
                return label
    return None


def extract_known(text: str) -> Dict[str, str]:
    t = _normalize(text)
    known: Dict[str, str] = {}

    v = _find_m2(t, ["под крышей", "общая площадь", "общая"])
    if v:
        known["area_under_roof_m2"] = f"{v} м²"

    v = _find_m2(t, ["внутри стен", "полезная", "жилая"])
    if v:
        known["area_inside_walls_m2"] = f"{v} м²"

    v = _find_m2(t, ["застек", "остеклен", "остекл"])
    if v:
        known["glazed_area_m2"] = f"{v} м²"

    v = _find_m2(t, ["2-й свет", "второй свет", "2й свет"])
    if v:
        known["second_light_m2"] = f"{v} м²"

    m = re.search(
        r"(?:этажность|этаж|этажа)\s*[:\-]?\s*(\d+(?:[.,]\d+)?)",
        t,
        re.IGNORECASE,
    )
    if m:
        known["floors"] = m.group(1).replace(",", ".")
    else:
        m = re.search(
            r"\b(одноэтажн|двухэтажн|трехэтажн)\w*\b", t, re.IGNORECASE
        )
        if m:
            w = m.group(1).lower()
            known["floors"] = (
                "1" if "одно" in w else "2" if "двух" in w else "3"
            )

    roof_type = _pick_one(
        t,
        {
            "двускатная": ["двускатная", "двускат"],
            "вальмовая": ["вальмовая", "вальма"],
            "плоская": ["плоская", "плоскую"],
            "односкатная": ["односкатная", "односкат"],
        },
    )
    if roof_type:
        known["roof_type"] = roof_type

    structure = _pick_one(
        t,
        {
            "каркас": ["каркас", "каркасный"],
            "газобетон": ["газобетон", "газик", "гб"],
            "кирпич": ["кирпич", "кирпичный"],
            "брус": ["брус", "клееный брус"],
            "монолит": ["монолит", "монолитный"],
        },
    )
    if structure:
        known["structure"] = structure

    foundation = _pick_one(
        t,
        {
            "плита": ["плита", "ушп", "монолитная плита"],
            "лента": ["лента", "ленточный"],
            "сваи": ["сваи", "свайный"],
            "ростверк": ["ростверк"],
        },
    )
    if foundation:
        known["foundation"] = foundation

    if re.search(r"\bрассроч", t, re.IGNORECASE):
        known["installments"] = "обсудить"
    if re.search(r"\bсептик\b", t, re.IGNORECASE):
        known["septic"] = "обсудить"

    return known


def is_filled(collected: Dict[str, str], field: str) -> bool:
    return bool((collected.get(field) or "").strip())


def compute_pending(collected: Dict[str, str]) -> List[str]:
    return [k for k in FIELDS.keys() if not is_filled(collected, k)]


def format_house_summary(d: Dict[str, str]) -> str:
    return (
        "🧾 Черновик заявки на дом:\n\n"
        f"Под крышей (м²): {d.get('area_under_roof_m2') or '-'}\n"
        f"Внутри стен (м²): {d.get('area_inside_walls_m2') or '-'}\n"
        f"Застеклённые (м²): {d.get('glazed_area_m2') or '-'}\n"
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
    if d.get("floors"):
        parts.append(f"{d['floors']} эт.")
    if d.get("area_under_roof_m2"):
        parts.append(f"{d['area_under_roof_m2']}")
    if d.get("structure"):
        parts.append(d["structure"])
    return "Дом • " + (" • ".join(parts) if parts else "заявка")


async def ask_next_question(m: Message, state: FSMContext) -> None:
    data = await state.get_data()
    collected: Dict[str, str] = dict(data.get("collected") or {})
    pending: List[str] = list(data.get("pending") or [])

    if not pending:
        pending = compute_pending(collected)

    if not pending:
        summary = (
            format_house_summary(collected)
            + "\nПодтверждаем отправку компаниям?"
        )
        await m.answer(summary, reply_markup=confirm_kb())
        await state.set_state(ClientHouseIntake.confirm)
        await state.update_data(current_field=None, pending=[])
        return

    field = pending[0]
    await state.update_data(current_field=field, pending=pending)
    await m.answer(FIELDS[field])


@router.callback_query(F.data == "role:client")
async def set_role_client(c: CallbackQuery):
    await set_user_role(c.from_user.id, "client")
    await c.message.answer(
        "Ок, вы клиент. Откроем меню:", reply_markup=client_menu_kb()
    )
    await c.answer()


@router.callback_query(F.data == "client:new")
async def new_request(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.answer("Опишите, какой дом вы хотите построить.")
    await state.set_state(ClientHouseIntake.describe)
    await c.answer()


@router.message(ClientHouseIntake.describe)
async def house_describe(m: Message, state: FSMContext):
    collected = extract_known(m.text or "")
    pending = compute_pending(collected)

    await state.update_data(
        collected=collected, pending=pending, current_field=None
    )

    if not pending:
        summary = (
            format_house_summary(collected)
            + "\nПодтверждаем отправку компаниям?"
        )
        await m.answer(summary, reply_markup=confirm_kb())
        await state.set_state(ClientHouseIntake.confirm)
        return

    await state.set_state(ClientHouseIntake.clarify)
    await ask_next_question(m, state)


@router.message(ClientHouseIntake.clarify)
async def house_clarify(
    m: Message, state: FSMContext, ai_intake: AIIntakeService
):
    data = await state.get_data()
    collected: Dict[str, str] = dict(data.get("collected") or {})
    pending: List[str] = list(data.get("pending") or [])
    current_field: Optional[str] = data.get("current_field")

    if not current_field:
        await ask_next_question(m, state)
        return

    # Сначала быстрый prefill правилами (вдруг пользователь ответил сразу на несколько полей)
    collected.update(extract_known(m.text or ""))
    await state.update_data(collected=collected)

    # Если prefill уже закрыл текущий вопрос — идём дальше без AI
    if is_filled(collected, current_field):
        if pending and pending[0] == current_field:
            pending = pending[1:]
        else:
            pending = compute_pending(collected)
        await state.update_data(pending=pending, current_field=None)
        await ask_next_question(m, state)
        return

    # AI решает: ответ есть/нужно уточнить/что сохранить
    eval_ = await ai_intake.evaluate(
        field_key=current_field,
        field_question=FIELDS[current_field],
        user_answer=m.text or "",
        collected=collected,
    )

    if eval_.need_clarify:
        await m.answer(
            eval_.clarify_question
            or ("Уточните, пожалуйста: " + FIELDS[current_field])
        )
        return

    if eval_.is_answered:
        # Сохраняем извлечённое значение
        if eval_.value and eval_.value.strip():
            collected[current_field] = eval_.value.strip()
        else:
            # если модель решила, что ответ есть, но value пустой — сохраним кратко сырой ответ
            collected[current_field] = (m.text or "").strip()[
                :200
            ] or "уточнить"

        await state.update_data(collected=collected)

        if pending and pending[0] == current_field:
            pending = pending[1:]
        else:
            pending = compute_pending(collected)

        await state.update_data(pending=pending, current_field=None)
        await ask_next_question(m, state)
        return

    # fallback: переспросим базовым вопросом
    await m.answer("Не до конца понял. " + FIELDS[current_field])


@router.callback_query(F.data == "client:confirm_edit")
async def confirm_edit(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.answer(
        "Ок, начнём заново. Опишите, какой дом вы хотите построить."
    )
    await state.set_state(ClientHouseIntake.describe)
    await c.answer()


@router.callback_query(F.data == "client:confirm_cancel")
async def confirm_cancel(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.answer(
        "Отменено. Меню клиента:", reply_markup=client_menu_kb()
    )
    await c.answer()


@router.callback_query(F.data == "client:confirm_yes")
async def confirm_yes(c: CallbackQuery, state: FSMContext):
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
    await c.answer()


@router.callback_query(F.data == "client:list")
async def my_requests(c: CallbackQuery):
    items = await list_requests_by_client(c.from_user.id)
    if not items:
        await c.message.answer(
            "У вас пока нет заявок.", reply_markup=client_menu_kb()
        )
        await c.answer()
        return

    await c.message.answer("📋 Ваши заявки:")
    for r in items[:10]:
        d = r["data"] or {}
        title = request_title(d)
        await c.message.answer(
            f"#{r['id']} • {title} • {r['status']}",
            reply_markup=request_open_kb(r["id"]),
        )
    await c.answer()


@router.callback_query(F.data.startswith("client:open:"))
async def open_request(c: CallbackQuery):
    req_id = int(c.data.split(":")[-1])
    req = await get_request(req_id)
    if not req or req["client_tg_id"] != c.from_user.id:
        await c.message.answer("Не нашёл эту заявку.")
        await c.answer()
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
    await c.answer()
