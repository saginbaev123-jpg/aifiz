from __future__ import annotations

import re
from typing import Iterable

_NULL_LINE = re.compile(r"(?im)^\s*(?:none|null|undefined|nan)\s*$")


def _clean_inline_math(part: str) -> str:
    # Streamlit/KaTeX accepts $...$ and $$...$$. Keep delimiters tight so the
    # literal dollar characters are not exposed as ordinary text.
    part = part.replace(r"\(", "$",).replace(r"\)", "$")
    part = part.replace(r"\[", "\n$$\n").replace(r"\]", "\n$$\n")
    part = re.sub(r"(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)", lambda m: "$" + m.group(1).strip() + "$", part)
    # Some model responses wrap display maths in plain square brackets.
    def bracket_formula(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        if any(token in inner for token in ("=", r"\frac", r"\sqrt", r"\vec", "^", "_", r"\cdot", r"\times")):
            return "\n$$\n" + inner + "\n$$\n"
        return match.group(0)
    part = re.sub(r"(?m)^\s*\[\s*([^\[\]\n]+)\s*\]\s*$", bracket_formula, part)
    part = re.sub(r"-{2,}>", "→", part)
    part = re.sub(r"<-{2,}", "←", part)
    part = re.sub(r"\${3,}", "$$", part)
    return part


def _split_columns(lines: Iterable[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        cols = [x.strip() for x in re.split(r"\s{2,}|\t+", line) if x.strip()]
        rows.append(cols)
    return rows


def _repair_fence(match: re.Match[str]) -> str:
    lang = match.group(1).strip().lower()
    body = match.group(2)
    # Real code must remain byte-for-byte intact.
    if lang not in ("", "text", "plaintext", "latex", "math"):
        return match.group(0)
    looks_math = "$" in body or bool(re.search(r"\\(?:frac|text|sqrt|vec|theta|Delta)", body))
    looks_diagram = bool(re.search(r"(?:→|←|↑|↓|-->|<--|\|)", body))
    if not (looks_math or looks_diagram):
        return match.group(0)

    rows = _split_columns(body.splitlines())
    # Convert explanatory 2-column ASCII layouts to a proper Markdown table.
    if len(rows) >= 2 and all(len(row) == 2 for row in rows):
        head = rows[0]
        rest = rows[1:]
        value = "\n| " + " | ".join(head) + " |\n| --- | --- |\n"
        value += "\n".join("| " + " | ".join(row) + " |" for row in rest) + "\n"
        return _clean_inline_math(value)
    return "\n" + _clean_inline_math(body.strip()) + "\n"


def sanitize_text(text: str | None) -> str:
    """Remove backend sentinel values without deleting legitimate prose."""
    value = str(text or "").replace("\u00a0", " ").replace("\x00", "")
    value = _NULL_LINE.sub("", value)
    # Typical serialized placeholders that occasionally leak from generated JSON.
    value = re.sub(r"(?im)^\s*(?:result|content|text)\s*:\s*(?:none|null)\s*$", "", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def prepare_math(text: str | None) -> str:
    """Prepare AI prose for Streamlit Markdown + KaTeX rendering.

    - preserves genuine source-code blocks;
    - repairs common LaTeX delimiter variants;
    - removes leaked None/null sentinel lines;
    - converts simple two-column pseudo-layouts into Markdown tables.
    """
    value = sanitize_text(text)
    if not value:
        return ""
    value = re.sub(r"```([^\n]*)\n(.*?)```", _repair_fence, value, flags=re.S)
    pieces = re.split(r"(```.*?```|`[^`\n]+`)", value, flags=re.S)
    for i in range(0, len(pieces), 2):
        pieces[i] = _clean_inline_math(pieces[i])
    return sanitize_text("".join(pieces))
