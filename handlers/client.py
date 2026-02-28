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
from keyboards import client_menu_kb, confirm_kb, request_open_kb, back_to_menu_kb
from states import ClientIntake
from services.broadcast import broadcast_request

router = Router()


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
    await c.message.answer("AI-ассистент: что вы ищете/какой продукт нужен? (1/4)")
    await state.set_state(ClientIntake.need)
    await c.answer()


@router.message(ClientIntake.need)
async def intake_need(m: Message, state: FSMContext):
    await state.update_data(need=m.text.strip())
    await m.answer("AI-ассистент: город/район? (2/4)")
    await state.set_state(ClientIntake.city)


@router.message(ClientIntake.city)
async def intake_city(m: Message, state: FSMContext):
    await state.update_data(city=m.text.strip())
    await m.answer("AI-ассистент: бюджет/диапазон? (3/4)")
    await state.set_state(ClientIntake.budget)


@router.message(ClientIntake.budget)
async def intake_budget(m: Message, state: FSMContext):
    await state.update_data(budget=m.text.strip())
    await m.answer("AI-ассистент: ограничения/комментарии? (4/4)")
    await state.set_state(ClientIntake.constraints)


@router.message(ClientIntake.constraints)
async def intake_constraints(m: Message, state: FSMContext):
    await state.update_data(constraints=m.text.strip())
    data = await state.get_data()
    summary = (
        "🧾 Черновик заявки:\n\n"
        f"Что нужно: {data.get('need')}\n"
        f"Город/район: {data.get('city')}\n"
        f"Бюджет: {data.get('budget')}\n"
        f"Ограничения: {data.get('constraints')}\n\n"
        "Подтверждаем отправку компаниям?"
    )
    await m.answer(summary, reply_markup=confirm_kb())
    await state.set_state(ClientIntake.confirm)


@router.callback_query(F.data == "client:confirm_edit")
async def confirm_edit(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Ок, начнём заново. Что нужно? (1/4)")
    await state.set_state(ClientIntake.need)
    await c.answer()


@router.callback_query(F.data == "client:confirm_cancel")
async def confirm_cancel(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.answer("Отменено. Меню клиента:", reply_markup=client_menu_kb())
    await c.answer()


@router.callback_query(F.data == "client:confirm_yes")
async def confirm_yes(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    req_id = await create_request(c.from_user.id, data)

    sent = await broadcast_request(c.bot, req_id, data)

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
        await c.message.answer("У вас пока нет заявок.", reply_markup=client_menu_kb())
        await c.answer()
        return

    await c.message.answer("📋 Ваши заявки:")
    for r in items[:10]:
        title = r["data"].get("need", "Заявка")
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

    data = req["data"]
    offers = await list_offers(req_id)

    text = (
        f"🧾 Заявка #{req_id}\n\n"
        f"Что нужно: {data.get('need')}\n"
        f"Город/район: {data.get('city')}\n"
        f"Бюджет: {data.get('budget')}\n"
        f"Ограничения: {data.get('constraints')}\n\n"
    )

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
