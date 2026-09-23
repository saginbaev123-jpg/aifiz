"""Strict, explainable grading of numeric physics answers."""
from __future__ import annotations

import re

NUMBER = re.compile(r"^\s*([-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?)\s*(.*?)\s*$")


def numeric_answer_matches(expected: str, answer: str, tolerance: float | None = None) -> bool:
    target = NUMBER.fullmatch(str(expected))
    submitted = NUMBER.fullmatch(str(answer))
    if not target or not submitted:
        return False
    expected_value = float(target.group(1).replace(",", "."))
    submitted_value = float(submitted.group(1).replace(",", "."))
    allowed = max(0.0, float(tolerance)) if tolerance is not None else max(0.01, abs(expected_value) * 0.02)
    expected_unit = re.sub(r"\s+", "", target.group(2)).lower().replace("²", "^2").replace("³", "^3")
    submitted_unit = re.sub(r"\s+", "", submitted.group(2)).lower().replace("²", "^2").replace("³", "^3")
    # A supplied unit must agree with the answer key. If no unit is in the key,
    # grading cannot infer the intended dimension from arbitrary generated text.
    return abs(expected_value - submitted_value) <= allowed and expected_unit == submitted_unit
