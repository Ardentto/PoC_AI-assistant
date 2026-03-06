import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from openai import AsyncOpenAI


JSON_SCHEMA = {
    "name": "intake_eval",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "is_answered": {"type": "boolean"},
            "need_clarify": {"type": "boolean"},
            "clarify_question": {"type": ["string", "null"]},
            "value": {"type": ["string", "null"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "notes": {"type": ["string", "null"]},
        },
        "required": [
            "is_answered",
            "need_clarify",
            "clarify_question",
            "value",
            "confidence",
            "notes",
        ],
    },
}


@dataclass(frozen=True)
class IntakeEval:
    is_answered: bool
    need_clarify: bool
    clarify_question: Optional[str]
    value: Optional[str]
    confidence: float
    notes: Optional[str]


class AIIntakeService:
    def __init__(self, api_key: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def evaluate(
        self,
        field_key: str,
        field_question: str,
        user_answer: str,
        collected: Dict[str, str],
    ) -> IntakeEval:
        system = (
            "Ты ассистент строительной компании. "
            "Тебе задают вопрос анкеты (field_question) и дают ответ клиента (user_answer). "
            "Определи, ответил ли клиент на этот вопрос.\n\n"
            "Правила:\n"
            "1) Если клиент ответил 'не знаю', 'не решил', 'не нужно', 'не требуется' — "
            "это тоже может считаться ответом (is_answered=true), если закрывает вопрос.\n"
            "2) Если ответ двусмысленный/неполный — need_clarify=true и дай короткий уточняющий вопрос.\n"
            "3) Если ответ содержит значение — извлеки value (строкой, человекочитаемо). "
            "Для площадей возвращай формат вроде '120 м²' если возможно.\n"
            "4) Верни строго JSON по схеме."
        )

        payload = {
            "field_key": field_key,
            "field_question": field_question,
            "user_answer": user_answer,
            "already_collected": collected,
            "hints": [
                "Если вопрос про рассрочку: value = 'да'/'нет'/'обсудить'/'не знаю'.",
                "Если вопрос про септик: value = 'нужен'/'не нужен'/'обсудить'/'не знаю'.",
                "Если вопрос про этажность: value например '1', '2', '1.5'.",
            ],
        }

        resp = await self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": JSON_SCHEMA["name"],  # <-- важно
                    "schema": JSON_SCHEMA["schema"],  # <-- важно
                    "strict": True,
                }
            },
        )

        # В разных версиях SDK удобное поле может отличаться — делаем максимально устойчиво
        raw = getattr(resp, "output_text", None)
        if not raw:
            # fallback: пробуем собрать текст из output
            raw = ""
            try:
                for item in resp.output:
                    for c in getattr(item, "content", []) or []:
                        if getattr(c, "type", None) in ("output_text", "text"):
                            raw += getattr(c, "text", "") or ""
            except Exception:
                pass

        data: Dict[str, Any] = json.loads(raw)

        return IntakeEval(
            is_answered=bool(data["is_answered"]),
            need_clarify=bool(data["need_clarify"]),
            clarify_question=data["clarify_question"],
            value=data["value"],
            confidence=float(data["confidence"]),
            notes=data["notes"],
        )
