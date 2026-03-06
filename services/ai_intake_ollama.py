import json
from dataclasses import dataclass
from typing import Dict, Optional

import httpx


@dataclass(frozen=True)
class IntakeEval:
    is_answered: bool
    need_clarify: bool
    clarify_question: Optional[str]
    value: Optional[str]
    confidence: float
    notes: Optional[str]


class AIIntakeService:
    """
    Локальный AI через Ollama.
    """

    def __init__(
        self,
        model: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434",
        timeout_sec: float = 60.0,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_sec

    async def _ollama_generate(self, prompt: str) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            # слегка уменьшаем "болтливость"
            "options": {"temperature": 0.2},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            return (data.get("response") or "").strip()

    @staticmethod
    def _extract_json(text: str) -> dict:
        """
        Пытаемся вытащить JSON даже если модель обернула его в текст/```json.
        """
        t = text.strip()

        # убрать ```json ... ```
        if t.startswith("```"):
            t = t.strip("`").strip()
            # иногда там "json\n{...}"
            if t.lower().startswith("json"):
                t = t[4:].strip()

        # найти первую { и последнюю }
        start = t.find("{")
        end = t.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("No JSON object found")
        return json.loads(t[start : end + 1])

    async def evaluate(
        self,
        field_key: str,
        field_question: str,
        user_answer: str,
        collected: Dict[str, str],
    ) -> IntakeEval:
        system_rules = (
            "Ты ассистент строительной компании cocать жестко. "
            "Нужно понять, ответил ли клиент на конкретный вопрос анкеты.\n\n"
            "Верни ТОЛЬКО валидный JSON без текста вокруг.\n"
            "Схема JSON:\n"
            "{\n"
            '  "is_answered": true/false,\n'
            '  "need_clarify": true/false,\n'
            '  "clarify_question": string|null,\n'
            '  "value": string|null,\n'
            '  "confidence": number (0..1),\n'
            '  "notes": string|null\n'
            "}\n\n"
            "Правила:\n"
            "1) Если клиент ответил 'не знаю', 'не решил', 'не нужно', 'не требуется' — "
            "это тоже может считаться ответом (is_answered=true), если закрывает вопрос.\n"
            "2) Если ответ двусмысленный/неполный — need_clarify=true и дай короткий уточняющий вопрос.\n"
            "3) Если ответ содержит значение — извлеки value (строкой). "
            "Для площадей пиши '130 м²'.\n"
            "4) Никакого markdown, никаких пояснений — только JSON.\n"
        )

        payload = {
            "field_key": field_key,
            "field_question": field_question,
            "user_answer": user_answer,
            "already_collected": collected,
        }

        prompt = (
            system_rules
            + "\nДанные:\n"
            + json.dumps(payload, ensure_ascii=False)
        )

        # 1-я попытка
        raw = await self._ollama_generate(prompt)
        try:
            data = self._extract_json(raw)
        except Exception:
            # 2-я попытка: просим "исправь и верни только JSON"
            raw2 = await self._ollama_generate(
                "Исправь ответ. Верни только валидный JSON по схеме. Вот твой прошлый ответ:\n"
                + raw
            )
            data = self._extract_json(raw2)

        return IntakeEval(
            is_answered=bool(data.get("is_answered")),
            need_clarify=bool(data.get("need_clarify")),
            clarify_question=data.get("clarify_question"),
            value=data.get("value"),
            confidence=float(data.get("confidence") or 0.0),
            notes=data.get("notes"),
        )
