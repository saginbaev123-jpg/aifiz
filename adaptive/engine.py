from __future__ import annotations

import random
from typing import Any

from config import LEVEL_A_MAX, LEVEL_B_MAX


LEVEL_RANK = {"A": 1, "B": 2, "C": 3}


class AdaptiveEngine:
    """Deterministic, explainable task selection for school use.

    The engine deliberately keeps the policy interpretable for teachers:
    mastery < 45 -> A, 45-75 -> B, > 75 -> C. Recent repeated mistakes can
    reduce the level by one step; a strong recent streak can increase it.
    """

    @staticmethod
    def level_from_mastery(score: float) -> str:
        if score < LEVEL_A_MAX:
            return "A"
        if score < LEVEL_B_MAX:
            return "B"
        return "C"

    @staticmethod
    def recommended_level(score: float, recent_attempts: list[dict[str, Any]] | None = None) -> str:
        level = AdaptiveEngine.level_from_mastery(score)
        if not recent_attempts:
            return level
        recent = recent_attempts[:4]
        valid = [a for a in recent if a.get("is_correct") is not None]
        if len(valid) >= 3:
            correct = sum(int(bool(a.get("is_correct"))) for a in valid[:3])
            if correct == 0:
                return "A"
            if correct == 3 and level == "A":
                return "B"
            if correct == 3 and level == "B":
                return "C"
        return level

    @staticmethod
    def choose_topic(mastery_rows: list[dict[str, Any]], due_topics: list[str] | None = None) -> str | None:
        if due_topics:
            due_set = set(due_topics)
            due_rows = [r for r in mastery_rows if r.get("topic") in due_set]
            if due_rows:
                return min(due_rows, key=lambda x: float(x.get("score", 50)))["topic"]
        if not mastery_rows:
            return None
        return min(mastery_rows, key=lambda x: float(x.get("score", 50)))["topic"]

    @staticmethod
    def select_task(
        tasks: list[dict[str, Any]],
        grade: int,
        topic: str,
        level: str,
        seen_question_ids: set[str] | None = None,
    ) -> dict[str, Any] | None:
        seen_question_ids = seen_question_ids or set()
        exact = [
            t for t in tasks
            if int(t.get("grade", grade)) == grade
            and t.get("topic") == topic
            and t.get("difficulty") == level
            and t.get("id") not in seen_question_ids
        ]
        if not exact:
            exact = [
                t for t in tasks
                if int(t.get("grade", grade)) == grade
                and t.get("topic") == topic
                and t.get("id") not in seen_question_ids
            ]
        if not exact:
            return None
        return random.choice(exact)

    @staticmethod
    def explanation(topic: str, mastery: float, level: str) -> str:
        if level == "A":
            return f"{topic}: меңгеру көрсеткіші {mastery:.0f}%. Негізгі ұғымды бекіту үшін A деңгейі таңдалды."
        if level == "B":
            return f"{topic}: меңгеру көрсеткіші {mastery:.0f}%. Білімді қолдануға арналған B деңгейі таңдалды."
        return f"{topic}: меңгеру көрсеткіші {mastery:.0f}%. Тереңдетілген қолдану үшін C деңгейі таңдалды."
