"""Student-facing, answer-specific feedback for completed online tests."""
from __future__ import annotations

from typing import Any


SKILL_LABELS = {
    "FORMULA_ERROR": "формуланы таңдау және қолдану",
    "SI_ERROR": "шамаларды SI жүйесіне айналдыру",
    "UNIT_ERROR": "өлшем бірліктерін тексеру",
    "CALCULATION_ERROR": "есептеу амалдарын тексеру",
    "CONCEPT_ERROR": "физикалық ұғымды түсіндіру",
    "VECTOR_ERROR": "векторлардың бағытын талдау",
    "GRAPH_ERROR": "графиктен дерек оқу",
    "READING_ERROR": "есептің шартын мұқият оқу",
}


def elapsed_label(seconds: int) -> str:
    seconds = max(0, int(seconds))
    minutes, remainder = divmod(seconds, 60)
    return f"{minutes} мин {remainder} с" if minutes else f"{remainder} с"


def question_feedback(row: dict[str, Any]) -> str:
    task = row.get("task") or {}
    if row.get("is_correct"):
        return "Жауабыңыз дұрыс. Осы тәсілді келесі есепте де қолданыңыз."
    skill = SKILL_LABELS.get(str(task.get("error_hint") or "").upper())
    if skill:
        return f"Дұрыс жауаппен салыстырыңыз; {skill} дағдысына назар аударыңыз."
    return "Дұрыс жауап пен шешу жолын салыстырып, осы сұрақты қайта орындаңыз."


def focus_recommendations(rows: list[dict[str, Any]], topic: str) -> list[str]:
    focus: list[str] = []
    for row in rows:
        if row.get("is_correct"):
            continue
        task = row.get("task") or {}
        area = str(task.get("topic") or topic).strip()
        skill = SKILL_LABELS.get(str(task.get("error_hint") or "").upper())
        label = f"{area}: {skill}" if area and skill else (skill or area)
        if label and label not in focus:
            focus.append(label)
    return focus
