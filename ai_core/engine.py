from __future__ import annotations

import json
import re
from html import unescape
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ai.openai_client import AIClient
from .config import CONFIG
from .context import build_context
from .generators import create_docx, create_pdf, create_pptx, create_physics_diagram_svg
from .permissions import PermissionManager
from .prompts import system_prompt
from .router import ToolRouter
from .tool_planner import ModelToolPlanner
from .visual_engine import diagram_prompt_contract, validate_diagram_spec, render_chart_svg


_INLINE_SVG_RE = re.compile(r"(?is)(?:```(?:svg|xml|html)?\s*)?(<svg\b.*?</svg>)(?:\s*```)?")
_INLINE_SVG_UNSAFE_RE = re.compile(r"(?is)<\s*(?:script|foreignObject|iframe|object|embed|image|a|style)\b|\son[a-z]+\s*=|javascript\s*:|\b(?:href|xlink:href)\s*=")


def _extract_inline_svg(text: str) -> tuple[str, list[str]]:
    """Separate leaked model SVG from assistant prose so source code is never shown in chat."""
    raw = str(text or "")
    raw = raw.replace("\\u003c", "<").replace("\\u003e", ">")
    for _ in range(2):
        dec = unescape(raw)
        if dec == raw:
            break
        raw = dec
    found: list[str] = []

    def repl(match: re.Match[str]) -> str:
        svg = match.group(1).strip()
        if _INLINE_SVG_UNSAFE_RE.search(svg):
            return ""
        found.append(svg)
        return "\n"

    cleaned = _INLINE_SVG_RE.sub(repl, raw)
    cleaned = re.sub(r"(?im)^\s*```(?:svg|xml|html)?\s*$", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, found


@dataclass
class Artifact:
    kind: str
    filename: str
    path: str
    mime: str
    title: str


@dataclass
class AIResult:
    text: str
    artifacts: list[Artifact] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)


class AICore:
    def __init__(self, db: Any, client: AIClient | None = None, output_root: Path | str = "generated_files"):
        self.db = db
        self.client = client or AIClient()
        self.router = ToolRouter()
        self.tool_planner = ModelToolPlanner(self.router)
        self.output_root = Path(output_root)

    def _write(self, user_id: int, conversation_id: int, name: str, data: bytes, kind: str, title: str, mime: str) -> Artifact:
        folder = self.output_root / str(user_id) / str(conversation_id)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / name
        target.write_bytes(data)
        self.db.add_generated_file(user_id, conversation_id, name, kind, str(target.resolve()), {"title": title})
        return Artifact(kind, name, str(target.resolve()), mime, title)

    def run(self, user: dict[str, Any], conversation_id: int, prompt: str, attachment_text: str = "", has_image: bool = False, image_bytes: bytes | None = None, image_mime: str = "image/jpeg") -> AIResult:
        started = time.perf_counter()
        role = str(user["role"])

        # Conversation state is loaded BEFORE planning.  This lets the model
        # understand follow-ups such as “осыны суретпен көрсет” or “алдыңғысын
        # графикпен бер” without brittle keyword matching.
        messages = self.db.messages(conversation_id, int(user["id"]), CONFIG.max_context_messages)
        generated = self.db.generated_files(conversation_id, int(user["id"]))
        prior = [m for m in messages if m.get("status") == "completed"]
        if prior and prior[-1]["sender"] == "user" and prior[-1]["text"] == prompt:
            prior = prior[:-1]
        self.client.conversation_messages = [
            {"role": m["sender"], "content": m["text"]}
            for m in prior if m["sender"] in {"user", "assistant"}
        ]

        semantic = self.tool_planner.plan(
            self.client, role, prompt, bool(attachment_text or image_bytes),
            image_bytes=image_bytes, image_mime=image_mime,
        )
        plan = semantic.plan
        for tool in plan.tools:
            PermissionManager.require(role, tool)

        context = build_context([], generated)
        request = prompt + ("\n\nЖасалған материалдар:\n" + context if context else "")
        if attachment_text:
            request += f"\n\nТіркелген файлдан алынған мәтін:\n{attachment_text[:24000]}"

        # A tool-call argument may be a clearer semantic restatement produced by
        # the model.  Keep the user's original wording, but give the executor the
        # restatement as additional intent rather than replacing the request.
        def tool_request(tool: str) -> str:
            args = plan.tool_args.get(tool, {}) if isinstance(getattr(plan, "tool_args", {}), dict) else {}
            rewritten = str(args.get("request") or "").strip() if isinstance(args, dict) else ""
            if rewritten and rewritten.casefold() != prompt.strip().casefold():
                return request + "\n\nЖИ анықтаған әрекет мақсаты: " + rewritten
            return request

        if "get_class_results" in plan.tools and role == "teacher":
            class_lines: list[str] = []
            for cls in self.db.teacher_classes(int(user["id"])):
                students = self.db.class_student_overview(int(cls["id"]))
                class_lines.append(f"{cls['name']}: {len(students)} оқушы")
                for row in students[:40]:
                    class_lines.append(f"- {row['full_name']}: әрекет {row.get('attempt_count') or 0}, сынып жұмысы {row.get('class_work_count') or 0}, PISA {row.get('pisa_work_count') or 0}")
            request += "\n\nРұқсат етілген сынып деректері:\n" + "\n".join(class_lines)

        artifacts: list[Artifact] = []
        # If the model decided that no tool is needed, its planner response is
        # already a context-aware answer.  Reuse it to avoid a second API call.
        content = semantic.direct_text if (semantic.used_model and plan.tools == ["chat"] and semantic.direct_text) else ""
        sys = system_prompt(role, plan.tools)
        sys += (
            "\nСұрақты алдыңғы диалогпен байланыстырып түсін. «Осы», «жалғастыр», «теориясын бер», "
            "«суретпен көрсет» дегенді соңғы талқыланған тақырыпқа қатысты қабылда. Жаңа тақырыпты пайдаланушы анық сұрағанда ғана ауыс. "
            "Формулаларды $...$ немесе жеке жолдағы $$...$$ арқылы жаз. Формула мен сызбаны код блогына салма; салыстыруға Markdown кестесін қолдан. "
            "Егер графикалық құрал орындалған болса, 'сурет сала алмаймын' немесе соған ұқсас шектеу туралы жазба; суреттің мағынасын түсіндір."
        )

        if image_bytes and "vision" in plan.tools:
            result = self.client.vision_json(sys, tool_request("vision") + '\nJSON: {"analysis":"...","steps":["..."]}', image_bytes, image_mime)
            content = str(result.get("analysis") or "").strip()
            if result.get("steps"):
                content += "\n\n" + "\n".join(f"{i+1}. {x}" for i, x in enumerate(result["steps"]))

        document_tools = [t for t in plan.tools if t in {"create_kmj", "create_bjb", "create_tjb", "create_pisa", "create_worksheet", "create_test"}]
        if document_tools or any(t in plan.tools for t in ("create_docx", "create_pdf", "create_pptx")):
            content = content or self.client.text(sys, request)
            title = prompt.strip().splitlines()[0][:90]
            if document_tools or "create_docx" in plan.tools:
                artifacts.append(self._write(user["id"], conversation_id, "material.docx", create_docx(title, content), "docx", title, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
            if "create_pdf" in plan.tools:
                artifacts.append(self._write(user["id"], conversation_id, "material.pdf", create_pdf(title, content), "pdf", title, "application/pdf"))
            if "create_pptx" in plan.tools:
                count = plan.slide_count or 7
                data = self.client.json(sys, tool_request("create_pptx") + f'\nДәл {count} слайд. JSON: {{"title":"...","slides":[{{"title":"...","bullets":["..."]}}]}}')
                slides = data.get("slides") if isinstance(data, dict) else []
                ptitle = str(data.get("title") or title)
                artifacts.append(self._write(user["id"], conversation_id, "presentation.pptx", create_pptx(ptitle, slides or [], count), "pptx", ptitle, "application/vnd.openxmlformats-officedocument.presentationml.presentation"))

        if "create_diagram" in plan.tools:
            drequest = tool_request("create_diagram")
            diagram_request = drequest + "\n\n" + diagram_prompt_contract(drequest)
            data = self.client.json(sys, diagram_request)
            dtitle = str(data.get("title") or prompt.strip().splitlines()[0][:90] or "Физикалық сызба").strip()
            spec = data.get("diagram") if isinstance(data.get("diagram"), dict) else data
            validated = validate_diagram_spec(spec if isinstance(spec, dict) else {}, context=drequest, title=dtitle)
            artifacts.append(self._write(
                user["id"], conversation_id, "diagram.svg",
                create_physics_diagram_svg(dtitle, validated.spec),
                "svg", dtitle, "image/svg+xml"
            ))
            explanation = str(data.get("explanation") or "").strip()
            if not explanation:
                # Explanatory prose is deliberately outside the image.  Ask the
                # model for natural chat text if the structured call omitted it.
                explanation = self.client.text(
                    sys,
                    drequest + "\n\nФизикалық сызба жасалды. Енді сурет ішіндегі белгілерді қайталай бермей, оның физикалық мағынасын оқушыға 2-5 абзацпен түсіндір. RAW SVG/JSON жазба."
                )
            content = content or explanation

        if "create_chart" in plan.tools:
            crequest = tool_request("create_chart")
            chart_request = crequest + """

Графикті RAW SVG/HTML емес, тек JSON дерек ретінде сипатта.
Физикалық тәуелділік пен өлшем бірліктері дұрыс болсын.
JSON: {"title":"...","type":"line|bar","x":[...],"y":[...],"x_label":"...","y_label":"..."}
"""
            chart = self.client.json(sys, chart_request)
            ctitle = str(chart.get("title") or "Физикалық график").strip()
            artifacts.append(self._write(
                user["id"], conversation_id, "chart.svg",
                render_chart_svg(chart, ctitle), "svg", ctitle, "image/svg+xml"
            ))
            content = content or self.client.text(sys, crequest + "\n\nГрафик жасалды. Оның негізгі физикалық мағынасын қысқа түсіндір.")

        if "create_image_background" in plan.tools or "create_image" in plan.tools:
            image_tool = "create_image_background" if "create_image_background" in plan.tools else "create_image"
            irequest = tool_request(image_tool)
            image_prompt = self.client.text(sys, irequest + "\nТек сурет генерациясына арналған нақты қысқа визуал сипаттама бер. Сурет ішінде мәтін/формула/сутаңба болмасын.")
            blob = self.client.image(image_prompt, size="1536x1024")
            is_bg = image_tool == "create_image_background"
            artifacts.append(self._write(user["id"], conversation_id, "presentation_background.png" if is_bg else "illustration.png", blob, "image", "Презентация фоны" if is_bg else "Көрнекі сурет", "image/png"))
            if not content:
                content = self.client.text(sys, irequest + "\n\nКөрнекі сурет жасалды. Егер сұраныс түсіндіруді де қажет етсе, суреттің оқу/физикалық мағынасын қысқа түсіндір; әйтпесе бір сөйлеммен дайын екенін айт.")

        if not content:
            content = self.client.text(sys, request)

        # Last-resort guard: raw/escaped model SVG can never leak into chat.
        content, leaked_svgs = _extract_inline_svg(content)
        for idx, svg in enumerate(leaked_svgs[:3], 1):
            name = "diagram.svg" if not any(a.filename == "diagram.svg" for a in artifacts) and idx == 1 else f"diagram_inline_{idx}.svg"
            artifacts.append(self._write(
                user["id"], conversation_id, name, svg.encode("utf-8"),
                "svg", "Физикалық сызба", "image/svg+xml"
            ))
        if leaked_svgs and not content.strip():
            content = "Физикалық сызба төменде көрсетілді."

        elapsed = int((time.perf_counter() - started) * 1000)
        for tool in plan.tools:
            self.db.record_tool_call(conversation_id, int(user["id"]), tool, {"has_attachment": bool(attachment_text or image_bytes), "routing": "model" if semantic.used_model else "fallback"}, "completed", elapsed)
        return AIResult(content, artifacts, plan.tools)
