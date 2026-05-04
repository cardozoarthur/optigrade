from __future__ import annotations

import json
import re
from dataclasses import dataclass

from openai import OpenAI

from app.core.config import settings


DAY_ALIASES = {
    "segunda": 0,
    "terca": 1,
    "terça": 1,
    "quarta": 2,
    "quinta": 3,
    "sexta": 4,
    "sabado": 5,
    "sábado": 5,
    "domingo": 6,
}


@dataclass(frozen=True)
class InterpretedConstraint:
    rule: dict
    confidence: float
    explanation: str


def interpret_teacher_constraint(text: str) -> InterpretedConstraint:
    if settings.openai_api_key:
        try:
            return _interpret_with_openai(text)
        except Exception:
            return _interpret_heuristically(text)
    return _interpret_heuristically(text)


def _interpret_with_openai(text: str) -> InterpretedConstraint:
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.responses.create(
        model=settings.openai_model,
        input=[
            {
                "role": "system",
                "content": (
                    "Converta restricoes docentes de grade universitaria em JSON. "
                    "Responda apenas JSON com keys: rule, confidence, explanation. "
                    "A rule deve usar type, days, start_minute, end_minute, preference e target."
                ),
            },
            {"role": "user", "content": text},
        ],
    )
    raw = response.output_text
    data = json.loads(raw)
    return InterpretedConstraint(
        rule=data.get("rule", {"type": "note", "text": text}),
        confidence=float(data.get("confidence", 0.5)),
        explanation=str(data.get("explanation", "Regra interpretada por IA.")),
    )


def _interpret_heuristically(text: str) -> InterpretedConstraint:
    normalized = text.lower().strip()
    days = [value for name, value in DAY_ALIASES.items() if name in normalized]
    start_minute, end_minute = _extract_time_window(normalized)

    rule_type = "note"
    preference = 0
    target = None

    if any(word in normalized for word in ["nao posso", "não posso", "indisponivel", "indisponível"]):
        rule_type = "availability"
        preference = -5
    elif any(word in normalized for word in ["prefiro", "preferencia", "preferência"]):
        rule_type = "preference"
        preference = 3
    elif any(word in normalized for word in ["posso", "disponivel", "disponível"]):
        rule_type = "availability"
        preference = 5

    if "manha" in normalized or "manhã" in normalized:
        start_minute, end_minute = 8 * 60, 12 * 60
    if "tarde" in normalized:
        start_minute, end_minute = 13 * 60, 18 * 60
    if "noite" in normalized:
        start_minute, end_minute = 18 * 60, 22 * 60

    course_match = re.search(r"(?:dar|ministrar|cadeira de|disciplina de)\s+(.+)$", normalized)
    if course_match:
        target = course_match.group(1).strip(" .")
        if rule_type == "note":
            rule_type = "course_preference"
            preference = 3

    rule = {
        "type": rule_type,
        "days": sorted(set(days)),
        "start_minute": start_minute,
        "end_minute": end_minute,
        "preference": preference,
        "target": target,
        "text": text,
    }
    return InterpretedConstraint(
        rule=rule,
        confidence=0.62 if rule_type != "note" else 0.35,
        explanation="Regra interpretada por heuristica local; confirme antes de usar como hard.",
    )


def _extract_time_window(text: str) -> tuple[int | None, int | None]:
    matches = re.findall(r"(\d{1,2})(?::(\d{2}))?\s*(?:h|horas)?", text)
    if not matches:
        return None, None
    minutes = []
    for hour, minute in matches[:2]:
        minutes.append(int(hour) * 60 + int(minute or 0))
    if len(minutes) == 1:
        return minutes[0], minutes[0] + 120
    return min(minutes), max(minutes)

