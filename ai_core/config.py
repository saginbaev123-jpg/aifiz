from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AIConfig:
    model: str = os.getenv("OPENAI_MODEL", "gpt-5.2")
    image_model: str = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")
    max_context_messages: int = int(os.getenv("AI_CONTEXT_MESSAGES", "18"))
    max_attachment_mb: int = int(os.getenv("AI_MAX_UPLOAD_MB", "20"))
    request_timeout: float = float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "180"))
    max_retries: int = int(os.getenv("AI_MAX_RETRIES", "3"))
    prompt_version: str = "2026-09-v1"


CONFIG = AIConfig()
