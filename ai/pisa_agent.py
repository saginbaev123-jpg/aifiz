from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PisaVisualPlan:
    visual_type: str
    reason: str = ""
    instruction: str = ""
    used_model: bool = False


def _tool(name: str, description: str) -> dict[str, Any]:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Why this visual is the most useful for this PISA task."},
                "instruction": {"type": "string", "description": "What exact evidence/data the visual must contain so at least one question depends on it."},
            },
            "required": ["reason", "instruction"],
            "additionalProperties": False,
        },
        "strict": True,
    }


PISA_VISUAL_TOOLS = [
    _tool("use_table", "Choose a data table when comparing several objects/cases or when exact values must be read and compared."),
    _tool("use_bar_chart", "Choose a bar chart when categories or discrete alternatives need quantitative comparison."),
    _tool("use_line_chart", "Choose a line graph when a continuous dependence, time series, experimental trend, or change of one variable with another is central."),
    _tool("use_physics_diagram", "Choose a physics schematic when spatial relations, forces, vectors, rays, circuits, fields, mechanisms, energy/heat flow, or motion geometry are central and physical correctness matters."),
    _tool("use_context_image", "Choose a generated contextual illustration/photo-like scene only when visual observation of a real-life setup/context helps the task and a precise physics diagram is not the main evidence."),
    _tool("use_no_visual", "Choose no visual only when a visual would be decorative or redundant and the PISA reasoning is better based purely on the scenario text."),
]

_CALL_TO_TYPE = {
    "use_table": "table",
    "use_bar_chart": "bar",
    "use_line_chart": "line",
    "use_physics_diagram": "diagram",
    "use_context_image": "image",
    "use_no_visual": "none",
}


def choose_pisa_visual(
    ai: Any,
    *,
    grade: int,
    topic: str,
    learning_goal: str = "",
    preference: str = "auto",
) -> PisaVisualPlan:
    pref = str(preference or "auto").strip().lower()
    if pref == "":
        pref = "auto"
    if pref in {"table", "bar", "line", "diagram", "image", "none"}:
        return PisaVisualPlan(pref, reason="Мұғалім қолмен таңдады.", instruction="Таңдалған көрнекілік тапсырманы шешуге қажетті дерек берсін.", used_model=False)

    system = (
        "You are the visual planner for a school physics PISA task. Understand the teacher's natural-language request semantically. "
        "Choose exactly one tool. The visual must be useful evidence for solving at least one question, not decoration. "
        "Prefer a deterministic physics diagram over a generated image whenever exact geometry/vectors/forces/rays/circuit connections matter. "
        "Prefer a graph/table when students must interpret quantitative data. A contextual generated image is for observation/context, not for precise labels or numerical text. "
        "Choose no visual only if adding one would not improve functional scientific literacy."
    )
    user = f"Grade: {grade}\nTeacher request/topic: {topic}\nAdditional learning goal/requirements: {learning_goal or 'not specified'}"
    try:
        result = ai.tool_plan(system, user, PISA_VISUAL_TOOLS, tool_choice="required")
        calls = result.get("calls") if isinstance(result, dict) else []
        if calls:
            call = calls[0]
            vtype = _CALL_TO_TYPE.get(str(call.get("name") or ""))
            args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            if vtype:
                return PisaVisualPlan(
                    vtype,
                    reason=str(args.get("reason") or "").strip(),
                    instruction=str(args.get("instruction") or "").strip(),
                    used_model=True,
                )
    except Exception:
        pass

    # Semantic compatibility path if function calling is unavailable in an
    # older SDK/model.  The model still chooses by meaning before any local
    # heuristic is considered.
    try:
        data = ai.json(
            "Сен физика PISA тапсырмасына ең пайдалы көрнекілікті мағынасы бойынша таңдайтын жоспарлаушысың. "
            "Тек бір type таңда: table, bar, line, diagram, image, none. Көрнекілік кемінде бір сұраққа нақты керек болсын. "
            "Дәл вектор/күш/сәуле/тізбек/геометрия үшін diagram, сандық тәуелділік үшін graph, өмірлік көрініс үшін image таңда. Тек JSON бер.",
            f"Сынып: {grade}\nСұраныс: {topic}\nҚосымша талап: {learning_goal}\nJSON: {{\"type\":\"diagram\",\"reason\":\"...\",\"instruction\":\"...\"}}",
        )
        vtype = str(data.get("type") or "").strip().lower() if isinstance(data, dict) else ""
        if vtype in {"table", "bar", "line", "diagram", "image", "none"}:
            return PisaVisualPlan(vtype, str(data.get("reason") or "").strip(), str(data.get("instruction") or "").strip(), used_model=True)
    except Exception:
        pass

    # Safe last-resort fallback only if both semantic model paths fail.
    low = f"{topic} {learning_goal}".casefold()
    if any(x in low for x in ("график", "тәуелді", "уақыт", "температура", "жылдамдық", "өзгер", "trend", "time")):
        return PisaVisualPlan("line", instruction="Айнымалылардың сандық тәуелділігін көрсет.")
    if any(x in low for x in ("кесте", "салыстыр", "мәндер", "дерек", "table", "compare")):
        return PisaVisualPlan("table", instruction="Салыстыруға қажетті нақты мәндерді бер.")
    if any(x in low for x in ("қозғалыс", "кинемат", "еркін түсу", "жылу", "механизм")):
        return PisaVisualPlan("image", instruction="Жағдаяттың физикалық құбылысын көрнекі сурет арқылы көрсет.")
    if any(x in low for x in ("күш", "линза", "сәуле", "тізбек", "өріс", "vector", "circuit")):
        return PisaVisualPlan("diagram", instruction="Физикалық байланыстарды дәл схема түрінде көрсет.")
    return PisaVisualPlan("image", instruction="Өмірлік жағдаятты мәтінсіз контекстік иллюстрациямен көрсет.")
