from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from states.chat_states import ChatState

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.set_state(ChatState.chatting)
    await message.answer(
        "Ты вошёл в режим чата.\n"
        "Теперь отправляй сообщения — они будут пересланы собеседнику."
    )
