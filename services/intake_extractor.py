import re
from typing import Dict, List, Optional

HUMAN_QUESTIONS = {
    "client_name": "Как к вам обращаться?",
    "lead_location": "В каком районе или городе планируете строить дом?",
    "has_land": "У вас уже есть участок под строительство? Можно ответить: да / нет / в процессе.",
    "start_timeline": "Когда вам было бы удобно начать строительство?",
    "lead_contact": "Какой способ связи удобнее, кроме Telegram?",

    "purchase_goal": "Для чего вам дом: для постоянного проживания, как дача, для аренды или как инвестиция?",
    "budget": "Какой у вас примерно бюджет на дом? Можно просто написать диапазон, например: до 10 млн.",
    "area_under_roof_m2": "Какой примерно размер дома хотите? Например: 120–150 квадратных метров.",
    "area_inside_walls_m2": "Сколько полезной площади внутри дома вам хотелось бы?",
    "bedrooms": "Сколько спален вам примерно нужно?",
    "glazed_area_m2": "Насколько много остекления хотите: обычные окна или много панорамных?",
    "second_light_m2": "Хотите ли дом со вторым светом? Это когда часть дома без перекрытия между этажами, с высоким потолком.",
    "roof_type": "Какая крыша вам ближе: обычная двускатная, плоская или пока не принципиально?",
    "roof_style": "Есть ли предпочтения по внешнему стилю дома: современный, классический, скандинавский?",
    "structure": "Из какого материала хотите дом: каркас, газобетон, кирпич, брус? Если не знаете — напишите, я помогу.",
    "floors": "Сколько этажей рассматриваете: один, полтора или два?",
    "wall_finish": "Какой внешний вид фасада вам нравится: штукатурка, кирпич, дерево, планкен или пока без разницы?",
    "foundation": "Есть ли предпочтения по основанию дома: плита, лента, сваи? Если не знаете — это нормально.",
    "distance": "Насколько далеко участок находится от города?",
    "installments": "Нужна ли вам рассрочка или другой вариант поэтапной оплаты?",
    "septic": "Нужна ли автономная канализация (септик), или на участке уже есть центральная?",
}

FIELD_EXPLANATIONS = {
    "second_light_m2": "Второй свет — это когда в части дома нет перекрытия между этажами, и получается очень высокий потолок и больше света.",
    "roof_type": "Тип кровли — это форма крыши. Например: двускатная — классический домик, плоская — современный стиль.",
    "roof_style": "Стиль кровли — это скорее про внешний вид, насколько дом выглядит современно, классически или в скандинавском стиле.",
    "structure": "Конструктив — это из чего будет построен дом: каркас, газобетон, кирпич, брус и так далее.",
    "wall_finish": "Отделка стен — это как дом будет выглядеть снаружи: штукатурка, кирпич, дерево, панели.",
    "foundation": "Фундамент — это основание дома. Самые частые варианты: плита, лента или сваи.",
    "distance": "Удалённость — это насколько далеко участок находится от города или от места, откуда вам обычно удобно добираться.",
    "installments": "Рассрочка — это если платить не сразу всей суммой, а частями по этапам.",
    "septic": "Септик — это автономная канализация для участка, если нет подключения к центральной канализации.",
}

FIELDS = {
    "client_name": "Как к вам обращаться?",
    "lead_location": "Где планируете строить дом?",
    "has_land": "У вас уже есть участок? (да/нет/в процессе)",
    "start_timeline": "Когда хотите начать строительство?",
    "lead_contact": "Какой способ связи удобнее кроме Telegram?",

    "purchase_goal": "Для каких целей покупаете дом?",
    "budget": "Какой у вас ориентировочный бюджет?",
    "area_under_roof_m2": "Сколько м² под крышей (общая площадь)?",
    "bedrooms": "Сколько спален нужно?",
    "floors": "Сколько этажей хотите?",
    "structure": "Какой материал дома рассматриваете?",
}

OPTIONAL_FIELDS = {
    "area_inside_walls_m2": "Сколько м² внутри стен (полезная/жилая площадь)?",
    "glazed_area_m2": "Какая площадь остекления примерно?",
    "second_light_m2": "Нужен ли второй свет?",
    "roof_type": "Какой тип кровли рассматриваете?",
    "roof_style": "Какой стиль кровли или внешний стиль дома вам ближе?",
    "wall_finish": "Какая отделка фасада вам нравится?",
    "foundation": "Какой фундамент рассматриваете?",
    "distance": "На каком удалении объект находится от города?",
    "installments": "Нужна ли рассрочка?",
    "septic": "Нужен ли септик?",
}

NUM_RE = r"(\d+(?:[.,]\d+)?)"


def _norm(text: str) -> str:
    return " ".join((text or "").split())


def _find_m2(text: str, keywords: List[str]) -> Optional[str]:
    pattern = rf"({'|'.join(map(re.escape, keywords))}).{{0,30}}{NUM_RE}\s*(?:м2|м²|кв\.?\s*м|кв|квадрат(?:а|ов)?)"
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        return m.group(2).replace(",", ".") + " м²"

    pattern2 = rf"{NUM_RE}\s*(?:м2|м²|кв\.?\s*м|кв|квадрат(?:а|ов)?).{{0,30}}({'|'.join(map(re.escape, keywords))})"
    m2 = re.search(pattern2, text, re.IGNORECASE)
    if m2:
        return m2.group(1).replace(",", ".") + " м²"

    # Просто "130 квадратов"
    m3 = re.search(rf"{NUM_RE}\s*(?:квадрат(?:а|ов)?|кв(?:\.?\s*м)?)", text, re.IGNORECASE)
    if m3 and any(k.lower() in text.lower() for k in keywords):
        return m3.group(1).replace(",", ".") + " м²"

    return None


def _pick_one(text: str, options: Dict[str, List[str]]) -> Optional[str]:
    for label, keys in options.items():
        for k in keys:
            if re.search(rf"\b{re.escape(k)}\b", text, re.IGNORECASE):
                return label
    return None


def _extract_budget(text: str) -> Optional[str]:
    t = text.lower()

    m = re.search(r"до\s+(\d+(?:[.,]\d+)?)\s*(млн|миллион(?:ов|а)?|тыс|тысяч)", t)
    if m:
        num = m.group(1).replace(",", ".")
        unit = m.group(2)
        if unit.startswith("млн") or unit.startswith("миллион"):
            return f"до {num} млн ₽"
        return f"до {num} тыс ₽"

    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(млн|миллион(?:ов|а)?|тыс|тысяч)", t)
    if m:
        num = m.group(1).replace(",", ".")
        unit = m.group(2)
        if unit.startswith("млн") or unit.startswith("миллион"):
            return f"{num} млн ₽"
        return f"{num} тыс ₽"

    return None


def _extract_goal(text: str) -> Optional[str]:
    t = text.lower()

    if any(x in t for x in ["постоянного проживания", "постоянное проживание", "жить круглый год", "для семьи"]):
        return "постоянное проживание"
    if any(x in t for x in ["дача", "сезонное проживание", "на выходные", "летний дом"]):
        return "дача"
    if any(x in t for x in ["аренда", "сдавать", "сдачи"]):
        return "аренда"
    if any(x in t for x in ["инвестиция", "инвестиционный", "перепродажа"]):
        return "инвестиция"

    return None


def _extract_bedrooms(text: str) -> Optional[str]:
    t = text.lower()

    m = re.search(r"(\d+)\s*(?:спальн|спальни|спальня)", t)
    if m:
        return m.group(1)

    if "одна спальня" in t:
        return "1"
    if "две спальни" in t:
        return "2"
    if "три спальни" in t:
        return "3"
    if "четыре спальни" in t:
        return "4"

    return None


def extract_known(text: str) -> Dict[str, str]:
    t = _norm(text)
    known: Dict[str, str] = {}

    budget = _extract_budget(t)
    if budget:
        known["budget"] = budget

    goal = _extract_goal(t)
    if goal:
        known["purchase_goal"] = goal

    bedrooms = _extract_bedrooms(t)
    if bedrooms:
        known["bedrooms"] = bedrooms

    v = _find_m2(t, ["под крышей", "общая площадь", "общая", "размер дома", "дом"])
    if v:
        known["area_under_roof_m2"] = v

    v = _find_m2(t, ["внутри стен", "полезная", "жилая"])
    if v:
        known["area_inside_walls_m2"] = v

    v = _find_m2(t, ["застек", "остеклен", "остекл", "остекления", "панорамных окон"])
    if v:
        known["glazed_area_m2"] = v

    v = _find_m2(t, ["2-й свет", "второй свет", "2й свет", "двойной свет"])
    if v:
        known["second_light_m2"] = v

    m = re.search(r"(?:этажность|этаж|этажа)\s*[:\-]?\s*(\d+(?:[.,]\d+)?)", t, re.IGNORECASE)
    if m:
        known["floors"] = m.group(1).replace(",", ".")
    else:
        m = re.search(r"\b(одноэтажн|двухэтажн|трехэтажн|полутораэтажн)\w*\b", t, re.IGNORECASE)
        if m:
            w = m.group(1).lower()
            if "одно" in w:
                known["floors"] = "1"
            elif "двух" in w:
                known["floors"] = "2"
            elif "полутора" in w:
                known["floors"] = "1.5"
            else:
                known["floors"] = "3"

    roof_type = _pick_one(
        t,
        {
            "двускатная": ["двускатная", "двускат"],
            "вальмовая": ["вальмовая", "вальма"],
            "плоская": ["плоская", "плоскую"],
            "односкатная": ["односкатная", "односкат"],
        },
    )
    if roof_type:
        known["roof_type"] = roof_type

    roof_style = _pick_one(
        t,
        {
            "современный": ["современный", "минимализм", "хай-тек"],
            "классический": ["классический", "классика"],
            "скандинавский": ["сканди", "скандинавский"],
        },
    )
    if roof_style:
        known["roof_style"] = roof_style

    structure = _pick_one(
        t,
        {
            "каркас": ["каркас", "каркасный"],
            "газобетон": ["газобетон", "газик", "гб", "газоблок"],
            "кирпич": ["кирпич", "кирпичный"],
            "брус": ["брус", "клееный брус"],
            "монолит": ["монолит", "монолитный"],
        },
    )
    if structure:
        known["structure"] = structure

    foundation = _pick_one(
        t,
        {
            "плита": ["плита", "ушп", "монолитная плита"],
            "лента": ["лента", "ленточный"],
            "сваи": ["сваи", "свайный"],
            "ростверк": ["ростверк"],
        },
    )
    if foundation:
        known["foundation"] = foundation

    wall_finish = _pick_one(
        t,
        {
            "штукатурка": ["штукатурка", "оштукатуренный"],
            "кирпич": ["облицовочный кирпич", "кирпич"],
            "дерево": ["дерево", "планкен", "доска"],
            "сайдинг": ["сайдинг"],
        },
    )
    if wall_finish:
        known["wall_finish"] = wall_finish

    if re.search(r"\bрассроч", t, re.IGNORECASE):
        known["installments"] = "нужна/обсудить"

    if re.search(r"\bсептик\b", t, re.IGNORECASE):
        if re.search(r"\b(не нужен|не надо|не требуется)\b", t, re.IGNORECASE):
            known["septic"] = "не нужен"
        else:
            known["septic"] = "нужен/обсудить"

    if re.search(r"\bучасток\b", t, re.IGNORECASE):
        if re.search(r"\b(есть|имеется|уже есть)\b", t, re.IGNORECASE):
            known["has_land"] = "да"
        elif re.search(r"\b(нет|пока нет|ещё нет)\b", t, re.IGNORECASE):
            known["has_land"] = "нет"
        elif re.search(r"\b(в процессе|ищем|подбираем)\b", t, re.IGNORECASE):
            known["has_land"] = "в процессе"

    timeline = re.search(
        r"(в этом году|в следующем году|весной|летом|осенью|зимой|в ближайшие \d+ мес|через \d+ мес|как можно скорее|в ближайшее время)",
        t,
        re.IGNORECASE,
    )
    if timeline:
        known["start_timeline"] = timeline.group(1)

    return known


def is_filled(collected: Dict[str, str], field: str) -> bool:
    return bool((collected.get(field) or "").strip())


def compute_pending(collected: Dict[str, str]) -> List[str]:
    # Сначала спрашиваем только ключевые поля для консультации и рассылки.
    return [k for k in FIELDS.keys() if not is_filled(collected, k)]


def compute_optional_pending(collected: Dict[str, str]) -> List[str]:
    return [k for k in OPTIONAL_FIELDS.keys() if not is_filled(collected, k)]
