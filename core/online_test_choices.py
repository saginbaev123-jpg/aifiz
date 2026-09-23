"""Stable four-choice presentation for classroom online tests."""
from __future__ import annotations

import math
import random
from typing import Any

from ai.assessment import NUMBER, numeric_answer_matches


def online_test_choices(task: dict[str, Any]) -> list[str]:
    """Use authored choices, or derive numeric distractors without changing the answer key."""
    answer = str(task.get("answer") or "").strip()
    if not answer:
        return []
    authored = task.get("options")
    if isinstance(authored, list):
        options = [str(x).strip() for x in authored]
        if len(options) == 4 and len(set(options)) == 4 and answer in options and all(options):
            return options
        if any(options):
            return []

    match = NUMBER.fullmatch(answer)
    if not match:
        return []
    target = float(match.group(1).replace(",", "."))
    if not math.isfinite(target):
        return []
    unit = match.group(2).strip()
    try:
        tolerance = float(task["tolerance"]) if task.get("tolerance") is not None else None
    except (TypeError, ValueError):
        tolerance = None
    step = max(abs(target) * 0.25, 0.1, 2 * max(0.0, tolerance or 0.0))
    choices = [answer]
    for factor in (1, -1, 2, -2, 3, -3, 4, -4, 5, -5):
        value = target + factor * step
        text = f"{value:.10g}" + (f" {unit}" if unit else "")
        if text not in choices and not numeric_answer_matches(answer, text, tolerance):
            choices.append(text)
        if len(choices) == 4:
            break
    if len(choices) != 4:
        return []
    random.Random(str(task.get("question") or "") + answer).shuffle(choices)
    return choices
