from __future__ import annotations

from typing import Any


def build_learning_path(mastery_rows: list[dict[str, Any]], mistakes: list[dict[str, Any]], limit: int = 5) -> list[dict[str, str]]:
    """Оқу траекториясын нақты жиналған дерекке сүйеніп құрады.

    attempts=0 болған тақырыптарға жасанды 50% көрсетілмейді: олар «Дерек жеткіліксіз»
    деп белгіленіп, алдымен диагностика/тапсырма орындау ұсынылады.
    """
    mistake_freq: dict[str, int] = {}
    for m in mistakes:
        topic = str(m.get("topic") or "")
        if topic:
            mistake_freq[topic] = mistake_freq.get(topic, 0) + int(m.get("frequency", 1) or 1)

    def rank(row: dict[str, Any]) -> tuple[int, float]:
        attempts = int(row.get("attempts") or 0)
        if attempts <= 0:
            return (1, 999.0)
        score = float(row.get("score") or 0)
        return (0, score - mistake_freq.get(str(row.get("topic") or ""), 0) * 2)

    rows = sorted(mastery_rows, key=rank)
    path: list[dict[str, str]] = []
    for r in rows[:limit]:
        topic = str(r.get("topic") or "Тақырып")
        attempts = int(r.get("attempts") or 0)
        if attempts <= 0:
            path.append({
                "topic": topic,
                "score": "Дерек жеткіліксіз",
                "action": "Алдымен қысқа диагностика немесе осы тақырыптан бір тапсырма орындаңыз.",
            })
            continue

        score = float(r.get("score") or 0)
        if score < 45:
            action = "Негізгі ұғымды қысқаша қайталау → A деңгейіндегі 2 есеп → қате талдауы → қайта тексеру"
        elif score < 75:
            action = "B деңгейіндегі қолдану есебі → бір PISA тапсырмасы → қысқа қорытынды тест"
        else:
            action = "C деңгейіндегі күрделі есеп → өмірлік жағдаят → тақырыпты аралық қайталау"
        if mistake_freq.get(topic, 0) >= 2:
            action = "Қайталанатын қатені түзету → " + action
        path.append({"topic": topic, "score": f"{score:.0f}%", "action": action})
    return path
