from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def role_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Я клиент", callback_data="role:client")],
            [InlineKeyboardButton(text="Я компания", callback_data="role:company")],
        ]
    )


def client_menu_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Новая заявка", callback_data="client:new")],
            [InlineKeyboardButton(text="📋 Мои заявки", callback_data="client:list")],
        ]
    )


def confirm_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить и разослать",
                    callback_data="client:confirm_yes",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Исправить", callback_data="client:confirm_edit"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена", callback_data="client:confirm_cancel"
                )
            ],
        ]
    )


def request_card_for_company_kb(request_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💰 Откликнуться", callback_data=f"company:offer:{request_id}"
                )
            ]
        ]
    )


def request_open_kb(request_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔎 Открыть", callback_data=f"client:open:{request_id}"
                )
            ]
        ]
    )


def back_to_menu_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="common:menu")]
        ]
    )