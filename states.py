from aiogram.fsm.state import State, StatesGroup


class ClientIntake(StatesGroup):
    # оставлен, чтобы ничего не ломать в других местах
    need = State()
    city = State()
    budget = State()
    constraints = State()
    confirm = State()


class ClientHouseIntake(StatesGroup):
    describe = State()  # "опишите дом"
    clarify = State()  # уточняющие вопросы по одному
    confirm = State()  # подтверждение перед рассылкой


class CompanyOnboarding(StatesGroup):
    name = State()
    contact = State()


class CompanyOffer(StatesGroup):
    price = State()
    comment = State()
