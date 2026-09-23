from __future__ import annotations

import base64
import json
import os
import re
from typing import Any

try:
    from openai import OpenAI  # type: ignore
except Exception:  # allows the app to show a friendly unavailable state if dependency is missing
    OpenAI = None  # type: ignore

from config import DEFAULT_MODEL


class AIClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = (api_key or os.getenv("OPENAI_API_KEY") or "").strip()
        self.model = (model or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL).strip()
        timeout = float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "180"))
        retries = int(os.getenv("AI_MAX_RETRIES", "2"))
        self.client = OpenAI(api_key=self.api_key, timeout=timeout, max_retries=retries) if (self.api_key and OpenAI is not None) else None
        self.conversation_messages: list[dict[str, Any]] = []

    @property
    def available(self) -> bool:
        return self.client is not None

    def _conversation_input(self, user: str) -> list[dict[str, Any]]:
        return [*getattr(self, "conversation_messages", []), {"role": "user", "content": user}]

    def text(self, system: str, user: str) -> str:
        if not self.client:
            raise RuntimeError("ЖИ қызметі қолжетімсіз")
        response = self.client.responses.create(
            model=self.model,
            instructions=system,
            input=self._conversation_input(user),
        )
        return (getattr(response, "output_text", "") or "").strip()

    def tool_plan(
        self,
        system: str,
        user: str,
        tools: list[dict[str, Any]],
        *,
        image_bytes: bytes | None = None,
        mime_type: str = "image/jpeg",
        tool_choice: str | dict[str, Any] = "auto",
    ) -> dict[str, Any]:
        """Ask the Responses API to semantically choose one or more app functions.

        This is intentionally a planning call: the app executes the selected
        local capability afterwards.  The parser is defensive across recent SDK
        object/dict representations of response output items.
        """
        if not self.client:
            raise RuntimeError("ЖИ қызметі қолжетімсіз")
        history = list(getattr(self, "conversation_messages", []))
        if image_bytes:
            b64 = base64.b64encode(image_bytes).decode("ascii")
            current: dict[str, Any] = {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user},
                    {"type": "input_image", "image_url": f"data:{mime_type};base64,{b64}"},
                ],
            }
        else:
            current = {"role": "user", "content": user}
        response = self.client.responses.create(
            model=self.model,
            instructions=system,
            input=[*history, current],
            tools=tools,
            tool_choice=tool_choice,
            parallel_tool_calls=True,
        )
        calls: list[dict[str, Any]] = []
        for item in getattr(response, "output", []) or []:
            itype = getattr(item, "type", None) if not isinstance(item, dict) else item.get("type")
            if itype != "function_call":
                continue
            name = getattr(item, "name", None) if not isinstance(item, dict) else item.get("name")
            raw_args = getattr(item, "arguments", "{}") if not isinstance(item, dict) else item.get("arguments", "{}")
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except json.JSONDecodeError:
                args = {}
            calls.append({
                "name": str(name or ""),
                "arguments": args if isinstance(args, dict) else {},
                "call_id": (getattr(item, "call_id", None) if not isinstance(item, dict) else item.get("call_id")),
            })
        return {"text": (getattr(response, "output_text", "") or "").strip(), "calls": calls}

    def vision_json(self, system: str, user: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> dict[str, Any]:
        if not self.client:
            raise RuntimeError("ЖИ қызметі қолжетімсіз")
        b64 = base64.b64encode(image_bytes).decode("ascii")
        response = self.client.responses.create(
            model=self.model,
            instructions=system + "\nЖауапты тек жарамды JSON объект ретінде бер. Markdown қолданба.",
            input=[*getattr(self, "conversation_messages", []), {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user},
                    {"type": "input_image", "image_url": f"data:{mime_type};base64,{b64}"},
                ],
            }],
        )
        raw = (getattr(response, "output_text", "") or "").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, flags=re.S)
            if not match:
                raise
            return json.loads(match.group(0))

    def json(self, system: str, user: str) -> dict[str, Any]:
        raw = self.text(
            system + "\nЖауапты тек жарамды JSON объект ретінде бер. Markdown қолданба.",
            user,
        )
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, flags=re.S)
            if not match:
                raise
            return json.loads(match.group(0))

    def image(self, prompt: str, size: str = "1536x1024") -> bytes:
        if not self.client:
            raise RuntimeError("ЖИ қызметі қолжетімсіз")
        model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2").strip() or "gpt-image-2"
        client = self.client.with_options(timeout=float(os.getenv("AI_IMAGE_TIMEOUT_SECONDS", "240")))
        result = client.images.generate(model=model, prompt=prompt, size=size)
        item = result.data[0]
        b64 = getattr(item, "b64_json", None)
        if not b64:
            raise RuntimeError("Сурет генерациясы нәтиже қайтармады")
        return base64.b64decode(b64)
