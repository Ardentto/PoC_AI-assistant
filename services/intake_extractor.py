import re
from typing import Dict, List, Tuple

FIELDS = {
    "area_under_roof_m2": "Сколько м² под крышей (общая площадь)?",
    "area_inside_walls_m2": "Сколько м² внутри стен (полезная/жилая площадь)?",
    "glazed_area_m2": "Какая площадь застеклённых проёмов (м²) примерно?",
    "second_light_m2": "Нужен ли 2-й свет? Если да — сколько м²?",
    "roof_type": "Тип кровли: двускатная/вальмовая/плоская/другое?",
    "roof_style": "Стиль кровли/внешний вид (современный, классика и т.п.)?",
    "structure": "Конструктив: каркас, газобетон, кирпич, брус, монолит и т.д.?",
    "floors": "Этажность: 1 / 1.5 / 2 / 3?",
    "wall_finish": "Отделка стен: фасад (штукатурка/кирпич/сайдинг/планкен...) ?",
    "foundation": "Фундамент: плита/лента/сваи/ростверк?",
    "distance": "Удалённость/локация: где строить и насколько далеко от города?",
    "installments": "Нужна рассрочка? (да/нет/какие условия)",
    "septic": "Септик нужен? (да/нет/тип/производительность если знаете)",
}

NUM_RE = r"(\d+(?:[.,]\d+)?)"


def _find_m2(text: str, keywords: List[str]) -> str | None:
    # ищем: "120 м2", "120м²", "120 кв", "120 квадратов"
    pattern = rf"({'|'.join(map(re.escape, keywords))}).{{0,25}}{NUM_RE}\s*(?:м2|м²|кв\.?\s*м|кв|квадрат)"
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        return m.group(2).replace(",", ".")
    # вариант: число + слово рядом
    pattern2 = rf"{NUM_RE}\s*(?:м2|м²|кв\.?\s*м|кв|квадрат).{{0,25}}({'|'.join(map(re.escape, keywords))})"
    m2 = re.search(pattern2, text, re.IGNORECASE)
    if m2:
        return m2.group(1).replace(",", ".")
    return None


def extract_known(text: str) -> Dict[str, str]:
    t = " ".join((text or "").split())

    known: Dict[str, str] = {}

    # площади
    v = _find_m2(t, ["под крышей", "общая площадь", "общая"])
    if v:
        known["area_under_roof_m2"] = v

    v = _find_m2(t, ["внутри стен", "полезная", "жилая"])
    if v:
        known["area_inside_walls_m2"] = v

    v = _find_m2(t, ["застек", "остеклен", "остекл"])
    if v:
        known["glazed_area_m2"] = v

    v = _find_m2(t, ["2-й свет", "второй свет", "двойной свет"])
    if v:
        known["second_light_m2"] = v

    # этажность
    m = re.search(
        r"(?:этажность|этаж|этажа)\s*[:\-]?\s*(\d+(?:[.,]\d+)?)",
        t,
        re.IGNORECASE,
    )
    if m:
        known["floors"] = m.group(1).replace(",", ".")
    else:
        m = re.search(
            r"\b(одноэтажн|двухэтажн|трехэтажн)\w*\b", t, re.IGNORECASE
        )
        if m:
            word = m.group(1).lower()
            known["floors"] = (
                "1" if "одно" in word else "2" if "двух" in word else "3"
            )

    # кровля/конструктив/фундамент — по ключевым словам
    def pick_one(options: Dict[str, List[str]]) -> str | None:
        for label, keys in options.items():
            for k in keys:
                if re.search(rf"\b{re.escape(k)}\b", t, re.IGNORECASE):
                    return label
        return None

    roof_type = pick_one(
        {
            "двускатная": ["двускатная", "двускат"],
            "вальмовая": ["вальмовая", "вальма"],
            "плоская": ["плоская", "плоскую"],
            "односкатная": ["односкатная", "односкат"],
        }
    )
    if roof_type:
        known["roof_type"] = roof_type

    structure = pick_one(
        {
            "каркас": ["каркас", "каркасный"],
            "газобетон": ["газобетон", "газик", "гб"],
            "кирпич": ["кирпич", "кирпичный"],
            "брус": ["брус", "клееный брус"],
            "монолит": ["монолит", "монолитный"],
        }
    )
    if structure:
        known["structure"] = structure

    foundation = pick_one(
        {
            "плита": ["плита", "монолитная плита", "ушп"],
            "лента": ["лента", "ленточный"],
            "сваи": ["сваи", "свайный"],
        }
    )
    if foundation:
        known["foundation"] = foundation

    # рассрочка/септик — простые флаги
    if re.search(r"\bрассроч", t, re.IGNORECASE):
        known["installments"] = "нужна/обсудить"

    if re.search(r"\bсептик\b", t, re.IGNORECASE):
        known["septic"] = "нужен/обсудить"

    return known


def missing_fields(collected: Dict[str, str]) -> List[str]:
    return [k for k in FIELDS.keys() if not collected.get(k)]


def build_questions(missing: List[str], max_q: int = 6) -> str:
    # чтобы не завалить пользователя сразу 13 пунктами
    chunk = missing[:max_q]
    lines = ["Мне нужно уточнить несколько моментов:"]
    for i, k in enumerate(chunk, 1):
        lines.append(f"{i}) {FIELDS[k]}")
    lines.append("\nМожно ответить одним сообщением, списком.")
    return "\n".join(lines)
