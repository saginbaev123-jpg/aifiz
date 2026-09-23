from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


def quality_from_result(correct: bool, confidence: int, difficulty: str = "B") -> int:
    confidence = max(1, min(5, int(confidence)))
    if correct:
        return min(5, 3 + (1 if confidence >= 3 else 0) + (1 if confidence >= 5 else 0))
    # confidently wrong is a misconception, score it lower
    return 0 if confidence >= 4 else (1 if confidence >= 2 else 2)


def next_state(existing: dict[str, Any] | None, quality: int) -> dict[str, Any]:
    quality = max(0, min(5, int(quality)))
    easiness = float(existing.get("easiness", 2.5)) if existing else 2.5
    interval = int(existing.get("interval_days", 0)) if existing else 0
    repetitions = int(existing.get("repetition_count", 0)) if existing else 0

    if quality >= 3:
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 6
        else:
            interval = max(1, min(365, round(interval * easiness)))
        repetitions += 1
    else:
        repetitions = 0
        interval = 1

    delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    easiness = max(1.3, min(3.0, easiness + delta))
    now = _now()
    return {
        "easiness": round(easiness, 3),
        "interval_days": interval,
        "repetition_count": repetitions,
        "next_review": (now + timedelta(days=interval)).isoformat(),
        "last_quality": quality,
        "last_reviewed": now.isoformat(),
    }


def due_topics(states: list[dict[str, Any]], limit: int = 10) -> list[str]:
    now = _now()
    due: list[tuple[datetime, str]] = []
    for s in states:
        nr = s.get("next_review")
        if not nr:
            continue
        try:
            dt = datetime.fromisoformat(str(nr).replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt <= now:
            due.append((dt, str(s["topic"])))
    due.sort(key=lambda x: x[0])
    return [t for _, t in due[:limit]]
