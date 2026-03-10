import json
from dataclasses import dataclass
from typing import Dict, Optional

from openai import AsyncOpenAI


@dataclass(frozen=True)
class IntakeEval:
    is_answered: bool
    need_clarify: bool
    clarify_question: Optional[str]
    value: Optional[str]
    confidence: float
    notes: Optional[str]


class AIIntakeService:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.8,
    ):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model
        self.temperature = temperature

    async def evaluate(
        self,
        field_key: str,
        field_question: str,
        user_answer: str,
        collected: Dict[str, str],
    ) -> IntakeEval:
        prompt = f"""
Ты ассистент строительной компании.
Тебе нужно понять, ответил ли клиент на конкретный вопрос анкеты.

Верни только JSON:
{{
  "is_answered": true,
  "need_clarify": false,
  "clarify_question": null,
  "value": "130 м²",
  "confidence": 0.95,
  "notes": null
}}

Текущий ключ поля: {field_key}
Текущий вопрос: {field_question}
Уже собранные данные: {json.dumps(collected, ensure_ascii=False)}
Ответ клиента: {user_answer}

Правила:
- Если клиент явно ответил по существу, is_answered=true.
- Если ответ неполный или двусмысленный, need_clarify=true и задай короткий уточняющий вопрос.
- Для площадей value старайся давать в виде '130 м²'.
- Для да/нет вопросов сохраняй value как 'да', 'нет', 'обсудить', 'не знаю'.
- Не пиши ничего кроме JSON.
""".strip()

        resp = await self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {
                    "role": "system",
                    "content": "Ты извлекаешь структурированные данные из ответов клиента.",
                },
                {"role": "user", "content": prompt},
            ],
        )

        text = resp.choices[0].message.content.strip()

        # если модель завернула JSON в ```json ... ```
        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()

        data = json.loads(text)

        return IntakeEval(
            is_answered=bool(data.get("is_answered")),
            need_clarify=bool(data.get("need_clarify")),
            clarify_question=data.get("clarify_question"),
            value=data.get("value"),
            confidence=float(data.get("confidence") or 0.0),
            notes=data.get("notes"),
        )
