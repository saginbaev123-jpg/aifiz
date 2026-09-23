from __future__ import annotations

from typing import Any

from ai.openai_client import AIClient

ERROR_LABELS = {
    "FORMULA_ERROR": "Формуланы қате таңдау",
    "SI_ERROR": "SI жүйесіне ауыстырмау",
    "CALCULATION_ERROR": "Математикалық есептеу қатесі",
    "CONCEPT_ERROR": "Физикалық ұғымды түсінбеу",
    "VECTOR_ERROR": "Вектор бағытын шатастыру",
    "GRAPH_ERROR": "Графикті қате талдау",
    "UNIT_ERROR": "Өлшем бірлігі қатесі",
    "READING_ERROR": "Есеп шартын қате түсіну",
    "OTHER": "Басқа қате",
}


def local_classify(question: str, answer: str, correct_answer: str, expected_error: str | None = None) -> dict[str, str]:
    if expected_error in ERROR_LABELS:
        code = expected_error
    else:
        a = (answer or "").lower().replace(" ", "")
        q = (question or "").lower()
        if any(unit in q for unit in ["км/сағ", "см", "кдж", "г "]) and not any(x in a for x in ["м/с", "м", "дж", "кг"]):
            code = "SI_ERROR"
        elif any(sym in a for sym in ["=", "/", "*"]) and a != str(correct_answer).lower().replace(" ", ""):
            code = "FORMULA_ERROR"
        else:
            code = "CONCEPT_ERROR"
    return {
        "code": code,
        "label": ERROR_LABELS[code],
        "description": f"Жауап дұрыс шешімге әкелмеді. Негізгі ықтимал себеп: {ERROR_LABELS[code].lower()}.",
        "correction": "Формуладағы шамалардың мағынасын және өлшем бірліктерін қайта тексеріп, ұқсас есепті қайта орында.",
    }


def analyze_error(
    ai: AIClient,
    question: str,
    student_answer: str,
    correct_answer: str,
    solution: str,
    topic: str,
    expected_error: str | None = None,
) -> dict[str, str]:
    if not ai.available:
        return local_classify(question, student_answer, correct_answer, expected_error)
    try:
        data = ai.json(
            "Сен физика мұғалімісің. Оқушы қатесін педагогикалық тұрғыда жікте.",
            f"""Тақырып: {topic}
Сұрақ: {question}
Оқушы жауабы: {student_answer}
Дұрыс жауап: {correct_answer}
Дұрыс шешу: {solution}

Мына кодтардың бірін таңда: {', '.join(ERROR_LABELS.keys())}.
JSON: {{"code":"...","description":"...","correction":"..."}}""",
        )
        code = data.get("code", "OTHER")
        if code not in ERROR_LABELS:
            code = "OTHER"
        return {
            "code": code,
            "label": ERROR_LABELS[code],
            "description": str(data.get("description") or ERROR_LABELS[code]),
            "correction": str(data.get("correction") or "Ұқсас есепті қайта орында."),
        }
    except Exception:
        return local_classify(question, student_answer, correct_answer, expected_error)
