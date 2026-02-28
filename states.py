from aiogram.fsm.state import State, StatesGroup


class ClientIntake(StatesGroup):
    need = State()
    city = State()
    budget = State()
    constraints = State()
    confirm = State()


class CompanyOnboarding(StatesGroup):
    name = State()
    contact = State()


class CompanyOffer(StatesGroup):
    price = State()
    comment = State()
