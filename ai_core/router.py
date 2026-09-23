from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ToolPlan:
    tools: list[str] = field(default_factory=list)
    slide_count: int | None = None
    requires_attachment: bool = False
    tool_args: dict[str, dict] = field(default_factory=dict)


class ToolRouter:
    """Deterministic fallback router. Normal routing is model-first via ModelToolPlanner."""

    # Free-form users rarely type one exact command.  In Kazakh especially,
    # "суретін салып бер", "суретпен түсіндір", "сызбасын көрсет" etc.
    # must all reach the deterministic diagram renderer instead of plain chat.
    _DIAGRAM_PATTERNS = (
        re.compile(r"(?:суретпен|сызбамен|схемамен)\s+(?:түсіндір|көрсет|бейнеле)", re.I),
        re.compile(r"(?:сурет(?:ін|і|ке)?|сызба(?:сын|сы)?|схема(?:сын|сы)?|траектория(?:сын|сы)?|вектор(?:ын|ларын|ы)?|күштер(?:ді|ін)?|сәулелер(?:ді|ін)?|тізбек(?:ті|тің)?|өріс\s*сызықтар(?:ын|ы)?)\s*.{0,36}?(?:сал(?:ып|шы|ыңыз|ыңдар|ын)?|сыз(?:ып|шы|ыңыз|ыңдар|ын)?|бейнеле(?:п|ші|ңіз)?|көрсет(?:іп|ші|іңіз)?)", re.I),
        re.compile(r"(?:сал(?:ып|шы|ыңыз|ыңдар|ын)?|сыз(?:ып|шы|ыңыз|ыңдар|ын)?|бейнеле(?:п|ші|ңіз)?|көрсет(?:іп|ші|іңіз)?)\s*.{0,36}?(?:сурет|сызба|схема|траектория|вектор|күш|сәуле|тізбек|өріс)", re.I),
        re.compile(r"(?:нарисуй|изобрази|покажи)\s*.{0,48}?(?:схем|рисунк|траектор|вектор|сил|цеп|пол)", re.I),
    )

    RULES = [
        ("create_kmj", ("қмж", "қысқа мерзімді жоспар")),
        ("create_bjb", ("бжб",)),
        ("create_tjb", ("тжб",)),
        ("create_pisa", ("pisa", "пиза")),
        ("create_worksheet", ("жұмыс пара", "worksheet")),
        ("create_test", ("тест",)),
        ("create_pptx", ("презента", "слайд", "pptx")),
        ("create_docx", ("word", "docx")),
        ("create_pdf", ("pdf",)),
        ("create_image_background", ("фон жаса", "презентацияға фон", "background")),
        ("create_image", ("сурет жаса", "сурет сал", "суретін сал", "суретін салып", "суретпен көрсет", "суретпен түсіндір", "иллюстрация жаса", "көрнекі сурет")),
        ("create_diagram", ("сызба", "схема", "диаграмма", "сызбасын сал", "схемасын сал", "векторын сал", "векторларды сал", "траекториясын сал", "траекториясын көрсет", "күштерді сал", "сәулелерді сал", "тізбекті сал", "өріс сызықтарын сал")),
        ("create_chart", ("график", "chart")),
        ("get_class_results", ("сынып нәтиж", "әлсіз тақырып", "кім орындамаған", "көп қате")),
        ("get_student_history", ("оқушы тарих", "соңғы 10 жұмыс", "жұмысын талда")),
        ("web_search", ("интернеттен", "соңғы зерттеу", "желіден тап")),
        ("code_execution", ("есепте", "статистика", "модельде")),
    ]

    def plan(self, prompt: str, has_attachment: bool = False) -> ToolPlan:
        low = prompt.casefold()
        tools: list[str] = []
        for tool, needles in self.RULES:
            if any(n in low for n in needles):
                tools.append(tool)

        # Morphology-aware visual intent fallback.  Do not treat
        # "мына суретті түсіндір" with an uploaded image as a request to draw
        # a second picture; that is a vision task.
        attached_image_explain = has_attachment and bool(re.search(r"(?:мына\s+)?сурет(?:ті|ті\s+)?\s*(?:түсіндір|талда)", low))
        if not attached_image_explain and any(p.search(low) for p in self._DIAGRAM_PATTERNS):
            precise = any(word in low for word in ("сызба", "схема", "вектор", "траектория", "сәуле", "тізбек", "өріс сызық"))
            tools.append("create_diagram" if precise else "create_image")
        if "create_image" in tools and "create_diagram" in tools and not any(word in low for word in ("сызба", "схема", "вектор", "траектория", "сәуле", "тізбек")):
            tools.remove("create_diagram")

        if has_attachment:
            tools.insert(0, "vision" if any(x in low for x in ("сурет", "фото", "дәптер", "график")) else "analyze_file")
        if not tools:
            tools = ["chat"]
        # Background is an image subtype; do not also route it as a generic diagram.
        if "create_image_background" in tools:
            tools = [t for t in tools if t not in {"create_diagram", "create_image"}]
        match = re.search(r"(\d{1,2})\s*(?:слайд|бет)", low)
        return ToolPlan(list(dict.fromkeys(tools)), int(match.group(1)) if match else None, has_attachment)
