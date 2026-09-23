from __future__ import annotations

import mimetypes
import re
import secrets
from pathlib import Path

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".txt", ".md", ".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_MIME_PREFIXES = ("image/", "text/")
ALLOWED_MIMES = {
    "application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/octet-stream",
}


def safe_display_name(name: str) -> str:
    base = Path(name).name
    return re.sub(r"[^0-9A-Za-zА-Яа-яӘәҒғҚқҢңӨөҰұҮүҺһ._() -]", "_", base)[:180]


def validate_upload(name: str, mime: str, size: int, max_mb: int = 20) -> None:
    ext = Path(name).suffix.casefold()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Бұл файл түріне қолдау көрсетілмейді")
    if size <= 0 or size > max_mb * 1024 * 1024:
        raise ValueError(f"Файл көлемі {max_mb} МБ-тан аспауы керек")
    clean_mime = (mime or mimetypes.guess_type(name)[0] or "application/octet-stream").casefold()
    if clean_mime not in ALLOWED_MIMES and not clean_mime.startswith(ALLOWED_MIME_PREFIXES):
        raise ValueError("Файл пішімі мен мазмұны сәйкес емес")


def save_upload(root: Path, name: str, data: bytes, mime: str, max_mb: int = 20) -> tuple[str, Path]:
    validate_upload(name, mime, len(data), max_mb)
    display = safe_display_name(name)
    root.mkdir(parents=True, exist_ok=True)
    target = (root / f"{secrets.token_hex(16)}{Path(display).suffix.casefold()}").resolve()
    if root.resolve() not in target.parents:
        raise ValueError("Файл жолы жарамсыз")
    target.write_bytes(data)
    return display, target
