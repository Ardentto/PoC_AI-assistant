import re
from typing import Optional


# Грубые рабочие ориентиры для Московской области.
# Это не коммерческая смета, а консультативная эвристика для диалога.
# Используем немного "консервативные" цифры, чтобы не обещать лишнего.
BUDGET_RULES_MO = {
    "frame": {"price_per_m2": 80_000, "label": "каркас"},
    "aerated": {"price_per_m2": 105_000, "label": "газобетон"},
    "brick": {"price_per_m2": 135_000, "label": "кирпич"},
}


def parse_budget_to_rubles(budget_text: str) -> Optional[int]:
    if not budget_text:
        return None

    t = budget_text.lower().replace(" ", "")

    # до 10 млн
    m = re.search(r"до(\d+(?:[.,]\d+)?)млн", t)
    if m:
        return int(float(m.group(1).replace(",", ".")) * 1_000_000)

    # 10 млн
    m = re.search(r"(\d+(?:[.,]\d+)?)млн", t)
    if m:
        return int(float(m.group(1).replace(",", ".")) * 1_000_000)

    # до 800 тыс
    m = re.search(r"до(\d+(?:[.,]\d+)?)тыс", t)
    if m:
        return int(float(m.group(1).replace(",", ".")) * 1_000)

    m = re.search(r"(\d+(?:[.,]\d+)?)тыс", t)
    if m:
        return int(float(m.group(1).replace(",", ".")) * 1_000)

    # голое число
    m = re.search(r"(\d{6,9})", t)
    if m:
        return int(m.group(1))

    return None


def _format_money_short(value: int) -> str:
    if value >= 1_000_000:
        v = value / 1_000_000
        if v.is_integer():
            return f"{int(v)} млн ₽"
        return f"{v:.1f} млн ₽".replace(".", ",")
    if value >= 1_000:
        v = value / 1_000
        if v.is_integer():
            return f"{int(v)} тыс ₽"
        return f"{v:.1f} тыс ₽".replace(".", ",")
    return f"{value} ₽"


def suggest_by_budget(budget_rub: int) -> list[dict]:
    result = []

    for _, info in BUDGET_RULES_MO.items():
        area = int(budget_rub / info["price_per_m2"])
        if area >= 45:
            result.append(
                {
                    "material": info["label"],
                    "estimated_area_m2": area,
                    "price_per_m2": info["price_per_m2"],
                }
            )

    return result


def format_budget_hint(budget_text: str) -> Optional[str]:
    budget_rub = parse_budget_to_rubles(budget_text)
    if not budget_rub:
        return None

    variants = suggest_by_budget(budget_rub)
    if not variants:
        return None

    lines = [
        "Если ориентироваться на ваш бюджет по Московской области, можно смотреть примерно такие варианты:"
    ]
    for v in variants:
        lines.append(
            f"— {v['material'].capitalize()}: около {v['estimated_area_m2']} м² "
            f"(ориентир {_format_money_short(v['price_per_m2'])} за м²)"
        )

    lines.append(
        "Это грубая оценка для консультации: без учёта дорогой архитектуры, сложного участка, премиальной отделки и инженерии."
    )
    return "\n".join(lines)


def format_field_budget_hint(field_key: str, budget_text: str) -> Optional[str]:
    """
    Короткая подсказка именно под текущий уточняющий вопрос.
    """
    budget_rub = parse_budget_to_rubles(budget_text)
    if not budget_rub:
        return None

    variants = suggest_by_budget(budget_rub)
    if not variants:
        return None

    if field_key == "structure":
        shortlist = ", ".join(v["material"] for v in variants[:3])
        return (
            f"Если смотреть на ваш бюджет, чаще всего в него реалистично попадают такие материалы: {shortlist}. "
            "Что вам ближе?"
        )

    if field_key in {"area_under_roof_m2", "area_inside_walls_m2"}:
        best = variants[0]
        return (
            f"Если ориентироваться на ваш бюджет, дом из материала «{best['material']}» "
            f"обычно получается около {best['estimated_area_m2']} м². "
            "В каком диапазоне площади вам было бы комфортно?"
        )

    if field_key == "floors":
        best = variants[0]
        suggestion = (
            "При таком бюджете чаще всего разумно смотреть одноэтажный компактный дом"
            if best["estimated_area_m2"] <= 120
            else "При таком бюджете уже можно рассматривать и один, и два этажа"
        )
        return suggestion + ". Что вам ближе?"

    return None
