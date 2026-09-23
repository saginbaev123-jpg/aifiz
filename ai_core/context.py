from __future__ import annotations

from typing import Any


def build_context(messages: list[dict[str, Any]], generated: list[dict[str, Any]], limit: int = 18) -> str:
    recent = messages[-limit:]
    lines = [f"{'Пайдаланушы' if m['sender']=='user' else 'Ассистент'}: {m['text'][:3000]}" for m in recent if m["sender"] != "system"]
    if generated:
        lines.append("Осы чатта жасалған материалдар:")
        for f in generated[-8:]:
            meta = f.get("metadata") or {}
            lines.append(f"- {f['type']}: {f['filename']} ({meta.get('title','')})")
    return "\n".join(lines)
