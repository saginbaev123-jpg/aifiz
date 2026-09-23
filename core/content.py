from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import DATA_DIR


def load_json(name: str) -> Any:
    path = DATA_DIR / name
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def curriculum() -> dict[str, list[str]]:
    return load_json("curriculum.json")


def question_bank() -> list[dict[str, Any]]:
    return load_json("questions.json")


def pisa_bank() -> list[dict[str, Any]]:
    return load_json("pisa_tasks.json")


def topics_for_grade(grade: int) -> list[str]:
    return curriculum().get(str(grade), [])
