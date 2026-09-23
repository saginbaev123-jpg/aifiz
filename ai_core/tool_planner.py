from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .permissions import PermissionManager
from .router import ToolPlan, ToolRouter


# Public function names exposed to the model.  They intentionally describe
# capabilities rather than Kazakh/Russian trigger phrases: the model decides
# semantically which action is needed.
_FUNCTION_TO_INTERNAL = {
    "draw_physics_diagram": "create_diagram",
    "generate_context_image": "create_image",
    "generate_presentation_background": "create_image_background",
    "plot_physics_graph": "create_chart",
    "analyze_uploaded_image": "vision",
    "analyze_uploaded_file": "analyze_file",
    "create_kmj": "create_kmj",
    "create_bjb": "create_bjb",
    "create_tjb": "create_tjb",
    "create_pisa_material": "create_pisa",
    "create_worksheet": "create_worksheet",
    "create_test": "create_test",
    "create_word_document": "create_docx",
    "create_pdf_document": "create_pdf",
    "create_presentation": "create_pptx",
    "get_class_results": "get_class_results",
    "get_student_history": "get_student_history",
    "calculate_or_model": "code_execution",
}


def _fn(name: str, description: str, properties: dict[str, Any] | None = None, required: list[str] | None = None) -> dict[str, Any]:
    properties = properties or {}
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required or [],
            "additionalProperties": False,
        },
        "strict": True,
    }


def assistant_tool_definitions(role: str, has_attachment: bool = False) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = [
        _fn(
            "draw_physics_diagram",
            "Use only when the user explicitly asks for a precise schematic, vector diagram, circuit, graph-like diagram with exact labels, or exact geometry. A general request for a physics PICTURE/ILLUSTRATION goes to generate_context_image.",
            {"request": {"type": "string", "description": "What must be shown in the physics diagram."}},
            ["request"],
        ),
        _fn(
            "generate_context_image",
            "Use for a free-form illustrative or realistic image, including a physics situation such as a falling ball. Prefer this for an ordinary request to draw a picture (сурет салып бер). Exact mathematical axes or measured geometry require a schematic instead.",
            {"request": {"type": "string", "description": "Concise image intent and essential visual details."}},
            ["request"],
        ),
        _fn(
            "plot_physics_graph",
            "Use when the user wants a quantitative graph, chart, dependence, experimental curve, x(t), v(t), a(t), I(U), temperature-time graph, or similar plotted data.",
            {"request": {"type": "string", "description": "What relation/data the graph should show."}},
            ["request"],
        ),
        _fn(
            "calculate_or_model",
            "Use when a numerical computation, statistics, simulation, or mathematical model is explicitly useful. Do not call only for a simple explanatory answer.",
            {"request": {"type": "string"}},
            ["request"],
        ),
    ]
    if has_attachment:
        tools.extend([
            _fn(
                "analyze_uploaded_image",
                "Use to inspect or explain an uploaded image/photo/notebook page/graph. If the user says 'this picture', 'this notebook', or wants errors checked from the image, analyze the uploaded image instead of drawing a new one.",
                {"request": {"type": "string"}},
                ["request"],
            ),
            _fn(
                "analyze_uploaded_file",
                "Use to read, summarize, compare, or extract information from a non-image uploaded document/file.",
                {"request": {"type": "string"}},
                ["request"],
            ),
        ])

    if role == "teacher":
        tools.extend([
            _fn("create_kmj", "Create a ready-to-use short-term lesson plan (ҚМЖ).", {"request": {"type": "string"}}, ["request"]),
            _fn("create_bjb", "Create a БЖБ assessment with scoring/descriptors/answers.", {"request": {"type": "string"}}, ["request"]),
            _fn("create_tjb", "Create a ТЖБ assessment with scoring/descriptors/answers.", {"request": {"type": "string"}}, ["request"]),
            _fn("create_pisa_material", "Create a PISA-style physics learning/assessment material when asked from the assistant chat.", {"request": {"type": "string"}}, ["request"]),
            _fn("create_worksheet", "Create a classroom worksheet.", {"request": {"type": "string"}}, ["request"]),
            _fn("create_test", "Create a physics test/quiz.", {"request": {"type": "string"}}, ["request"]),
            _fn("create_word_document", "Create the requested material as a Word/DOCX file.", {"request": {"type": "string"}}, ["request"]),
            _fn("create_pdf_document", "Create the requested material as a PDF file.", {"request": {"type": "string"}}, ["request"]),
            _fn(
                "create_presentation",
                "Create a PPTX presentation. Use the requested slide count if one is stated; otherwise choose a sensible count.",
                {
                    "request": {"type": "string"},
                    "slide_count": {"type": ["integer", "null"], "minimum": 1, "maximum": 30},
                },
                ["request", "slide_count"],
            ),
            _fn("generate_presentation_background", "Generate a text-free 16:9 presentation background image.", {"request": {"type": "string"}}, ["request"]),
            _fn("get_class_results", "Use only when the teacher asks about their class results, weak topics, missing work, or aggregate student performance.", {"request": {"type": "string"}}, ["request"]),
            _fn("get_student_history", "Use only when the teacher asks for the work/history/progress of a student they are allowed to see.", {"request": {"type": "string"}}, ["request"]),
        ])
    return tools


@dataclass
class SemanticPlan:
    plan: ToolPlan
    direct_text: str = ""
    used_model: bool = False


class ModelToolPlanner:
    """Model-first semantic planner with deterministic fallback.

    The keyword router is retained only as a fail-safe for API/model/tool-call
    failures.  Normal operation lets the language model understand arbitrary
    phrasing and choose capabilities through function calling.
    """

    def __init__(self, fallback: ToolRouter | None = None):
        self.fallback = fallback or ToolRouter()

    def plan(self, client: Any, role: str, prompt: str, has_attachment: bool = False, *, image_bytes: bytes | None = None, image_mime: str = "image/jpeg") -> SemanticPlan:
        if not getattr(client, "available", False) or not hasattr(client, "tool_plan"):
            return SemanticPlan(self.fallback.plan(prompt, has_attachment), used_model=False)

        system = (
            "You are the capability router for AI Physics KZ. Understand the user's meaning, not keywords. "
            "The conversation can be in Kazakh, Russian, English, or mixed language. "
            "If a normal text answer is enough, answer briefly and do not call a function. "
            "If the user asks to DRAW/SHOW VISUALLY, never claim that you cannot draw when a relevant tool exists: "
            "use generate_context_image for an ordinary request to draw a picture, draw_physics_diagram only for an explicitly requested precise labelled schematic, "
            "and plot_physics_graph for quantitative graphs. Uploaded images should be analyzed, not redrawn, unless the user explicitly asks for a new drawing. "
            "Multiple functions may be selected when the request genuinely needs multiple outputs. "
            "Do not reveal function names or internal routing to the user."
        )
        try:
            result = client.tool_plan(
                system,
                prompt,
                assistant_tool_definitions(role, has_attachment),
                image_bytes=image_bytes if has_attachment else None,
                mime_type=image_mime,
            )
            calls = result.get("calls") if isinstance(result, dict) else []
            tools: list[str] = []
            args_by_tool: dict[str, dict[str, Any]] = {}
            slide_count: int | None = None
            for call in calls or []:
                name = str(call.get("name") or "")
                internal = _FUNCTION_TO_INTERNAL.get(name)
                if not internal or not PermissionManager.allowed(role, internal):
                    continue
                if internal not in tools:
                    tools.append(internal)
                args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
                args_by_tool[internal] = args
                if internal == "create_pptx":
                    try:
                        sc = args.get("slide_count")
                        slide_count = int(sc) if sc is not None else None
                    except (TypeError, ValueError):
                        slide_count = None
            direct_text = str(result.get("text") or "").strip() if isinstance(result, dict) else ""
            if not tools:
                tools = ["chat"]
            return SemanticPlan(
                ToolPlan(tools=tools, slide_count=slide_count, requires_attachment=has_attachment, tool_args=args_by_tool),
                direct_text=direct_text,
                used_model=True,
            )
        except Exception:
            # Compatibility path for older OpenAI SDK/model combinations that
            # do not expose Responses function calling yet.  It is still
            # semantic/model-based; keyword routing is only the final fail-safe.
            try:
                allowed = [t for t in (
                    "chat", "vision", "analyze_file", "code_execution", "create_diagram", "create_chart", "create_image",
                    "create_kmj", "create_bjb", "create_tjb", "create_pisa", "create_worksheet", "create_test",
                    "create_docx", "create_pdf", "create_pptx", "create_image_background", "get_class_results", "get_student_history"
                ) if PermissionManager.allowed(role, t)]
                data = client.json(
                    "Сен AI Physics KZ әрекет жоспарлаушысың. Пайдаланушының сөйлемін мағынасы бойынша түсін; кілт сөздерге байланба. "
                    "Қарапайым жауапқа chat таңда. Дәл физикалық сызба/траектория/вектор керек болса create_diagram, еркін/реалистік сурет керек болса create_image, "
                    "сандық график керек болса create_chart таңда. Тіркелген суретті талдау үшін vision таңда. Бірнеше әрекет шын қажет болса бірнешеуін таңда. "
                    "Тек JSON бер.",
                    f"Рөл: {role}\nТіркеме бар: {has_attachment}\nРұқсат етілген құралдар: {allowed}\nСұраныс: {prompt}\n"
                    'JSON: {"tools":["chat"],"slide_count":null}',
                )
                raw_tools = data.get("tools") if isinstance(data, dict) else []
                tools = [str(t) for t in raw_tools if str(t) in allowed] if isinstance(raw_tools, list) else []
                if not tools:
                    tools = ["chat"]
                sc = data.get("slide_count") if isinstance(data, dict) else None
                try:
                    slide_count = int(sc) if sc is not None else None
                except (TypeError, ValueError):
                    slide_count = None
                return SemanticPlan(ToolPlan(tools=list(dict.fromkeys(tools)), slide_count=slide_count, requires_attachment=has_attachment), used_model=True)
            except Exception:
                return SemanticPlan(self.fallback.plan(prompt, has_attachment), used_model=False)
