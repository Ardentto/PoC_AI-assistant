from aiogram.fsm.state import StatesGroup, State


class ChatState(StatesGroup):
    chatting = State()