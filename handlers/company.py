from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from db import (
    set_user_role,
    upsert_company,
    get_company_by_tg,
    upsert_offer,
    get_request,
)
from states import CompanyOnboarding, CompanyOffer

router = Router()


@router.callback_query(F.data == "role:company")
async def set_role_company(c: CallbackQuery, state: FSMContext):
    await set_user_role(c.from_user.id, "company")
    company = await get_company_by_tg(c.from_user.id)

    if company:
        await c.message.answer(
            f"Вы уже зарегистрированы как компания: {company['name']}.\n"
            "Ожидайте заявки — они будут приходить сюда."
        )
        await c.answer()
        return

    await c.message.answer("Регистрация компании. Введите название компании:")
    await state.set_state(CompanyOnboarding.name)
    await c.answer()


@router.message(CompanyOnboarding.name)
async def company_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text.strip())
    await m.answer("Контакт для клиента (телефон/ник/сайт):")
    await state.set_state(CompanyOnboarding.contact)


@router.message(CompanyOnboarding.contact)
async def company_contact(m: Message, state: FSMContext):
    data = await state.get_data()
    name = data["name"]
    contact = m.text.strip()

    await upsert_company(m.from_user.id, name, contact)
    await state.clear()
    await m.answer(
        f"✅ Компания зарегистрирована: {name}\n"
        "Теперь вы будете получать заявки сюда."
    )


@router.callback_query(F.data.startswith("company:offer:"))
async def start_offer(c: CallbackQuery, state: FSMContext):
    req_id = int(c.data.split(":")[-1])

    company = await get_company_by_tg(c.from_user.id)
    if not company:
        await c.message.answer("Сначала зарегистрируйтесь как компания через /start.")
        await c.answer()
        return

    req = await get_request(req_id)
    if not req:
        await c.message.answer("Заявка не найдена.")
        await c.answer()
        return

    await state.update_data(request_id=req_id)
    await c.message.answer(
        f"Отклик на заявку #{req_id}\nВведите цену (например: 120 000 ₽ или 10 000 ₽/мес):"
    )
    await state.set_state(CompanyOffer.price)
    await c.answer()


@router.message(CompanyOffer.price)
async def offer_price(m: Message, state: FSMContext):
    await state.update_data(price=m.text.strip())
    await m.answer("Комментарий (необязательно). Напишите текст или '-' :")
    await state.set_state(CompanyOffer.comment)


@router.message(CompanyOffer.comment)
async def offer_comment(m: Message, state: FSMContext):
    st = await state.get_data()
    req_id = int(st["request_id"])
    price = st["price"]
    comment = m.text.strip()
    if comment == "-":
        comment = ""

    company = await get_company_by_tg(m.from_user.id)
    if not company:
        await m.answer("Компания не найдена. Пройдите /start.")
        await state.clear()
        return

    await upsert_offer(req_id, company["id"], price, comment)

    # уведомляем клиента
    req = await get_request(req_id)
    client_id = req["client_tg_id"]

    await m.bot.send_message(
        chat_id=client_id,
        text=(
            f"📨 Новый отклик по заявке #{req_id}\n\n"
            f"Компания: {company['name']}\n"
            f"Контакт: {company['contact']}\n"
            f"Стоимость: {price}\n"
            f"Комментарий: {comment or '-'}"
        ),
    )

    await state.clear()
    await m.answer("✅ Отклик отправлен клиенту.")
