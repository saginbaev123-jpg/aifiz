"""Compare only equivalent topic assessments with the same question count."""
from __future__ import annotations

from typing import Any


def paired_diagnostics(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(history, key=lambda d: (d.get("created_at", ""), d.get("id", 0)))
    open_baselines: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for run in ordered:
        topic = run.get("focus_topic")
        if not topic:
            continue  # Legacy mixed-topic tests are not comparable.
        if run.get("phase") == "baseline":
            open_baselines[topic] = run
        elif run.get("phase") == "final" and topic in open_baselines:
            base = open_baselines[topic]
            if int(base["total"]) != int(run["total"]):
                continue
            open_baselines.pop(topic)
            rows.append({
                "Тақырып": topic,
                "Бастапқы": float(base["percent"]),
                "Қорытынды": float(run["percent"]),
                "Өзгеріс (п.т.)": round(float(run["percent"]) - float(base["percent"]), 1),
                "Сұрақ саны": int(run["total"]),
                "Бастапқы күні": str(base["created_at"])[:10],
                "Қорытынды күні": str(run["created_at"])[:10],
            })
    return rows
