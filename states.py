from aiogram.fsm.state import State, StatesGroup


class ClientLeadFlow(StatesGroup):
    lead_name = State()
    lead_location = State()
    lead_has_land = State()
    lead_timeline = State()
    lead_contact = State()
    wait_voice = State()
    clarify = State()
    confirm = State()


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
