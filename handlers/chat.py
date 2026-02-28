from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from states.chat_states import ChatState
from services.chat_service import ChatService

router = Router()
chat_service = ChatService()

# ⚠️ ВРЕМЕННО: вручную соединяем двух людей
USER_1 = 123456789
USER_2 = 987654321

chat_service.connect_users(USER_1, USER_2)


@router.message(ChatState.chatting, F.text)
async def chat_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    partner_id = chat_service.get_partner(user_id)

    if not partner_id:
        await message.answer("У тебя нет собеседника.")
        return

    await message.bot.send_message(
        chat_id=partner_id,
        text=f"Сообщение от {message.from_user.full_name}:\n\n{message.text}"
    )
