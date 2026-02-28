from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from keyboards import role_kb, client_menu_kb
from db import get_user_role

router = Router()


@router.message(F.text == "/start")
async def start(m: Message):
    await m.answer("Привет! Выберите роль для PoC:", reply_markup=role_kb())


@router.callback_query(F.data == "common:menu")
async def back_to_menu(c: CallbackQuery):
    role = await get_user_role(c.from_user.id)
    if role == "client":
        await c.message.answer("Меню клиента:", reply_markup=client_menu_kb())
    elif role == "company":
        await c.message.answer(
            "Меню компании:\nОжидайте заявки — они будут приходить сюда."
        )
    else:
        await c.message.answer("Выберите роль:", reply_markup=role_kb())
    await c.answer()
