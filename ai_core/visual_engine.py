from __future__ import annotations

"""Universal visual planning and validation for school physics.

The AI may suggest structured data, but this module decides which visual family is
appropriate, repairs unsafe/mismatched diagram specs, and provides deterministic
fallbacks.  It deliberately never accepts raw SVG/HTML from a model.
"""

from dataclasses import dataclass, field
from html import escape
import math
import re
from typing import Any

DIAGRAM_TYPES = {
    "linear_motion", "accelerated_motion", "free_fall", "projectile_motion",
    "circular_motion", "rotating_platform", "forces", "inclined_plane",
    "energy_conversion", "momentum_collision", "pressure_buoyancy",
    "fluid_pressure", "heat_transfer", "phase_change", "gas_process",
    "oscillation", "spring", "wave", "ray_optics", "lens", "mirror",
    "electric_circuit", "electric_field", "magnetic_field",
    "electromagnetic_induction", "lever", "pulley", "measurement",
    "generic_physics_scene",
}

AXIS_DIAGRAM_TYPES = {"projectile_motion"}
SEMANTIC_TEMPLATE_TYPES = DIAGRAM_TYPES - {"generic_physics_scene", "measurement"}


@dataclass
class ValidationResult:
    spec: dict[str, Any]
    confidence: float
    errors: list[str] = field(default_factory=list)
    repaired: bool = False


def _low(text: Any) -> str:
    return str(text or "").casefold().replace("ё", "е")


def infer_diagram_type(text: str) -> str:
    """Classify common 7–11 grade physics visuals using deterministic topic signals."""
    low = _low(text)

    rules: list[tuple[str, tuple[str, ...]]] = [
        ("rotating_platform", ("айналмалы платформа", "айналатын платформа", "бұрыштық жылдамдық", "айналу периоды", "айналу осі", "ω", "омега")),
        ("circular_motion", ("центрге тарт", "центрге ұмт", "шеңбер бой", "шеңберлік қозғ", "дөңгелек бой", "центрипет")),
        ("projectile_motion", ("көкжиекке бұрыш", "горизонтқа бұрыш", "лақтырылған дене", "лақтыру бұрышы", "параболалық траектория", "парабола")),
        ("free_fall", ("еркін түсу", "еркін құлау", "тік төмен құлау", "g үдеуі", "ауырлық үдеуі")),
        ("accelerated_motion", ("теңүдемелі", "бірқалыпты үдемелі", "үдемелі қозғалыс", "тежелу", "үдеу тұрақты")),
        ("inclined_plane", ("көлбеу жазық", "наклонная плоскость", "еңіс бет")),
        ("forces", ("еркін дене диаграм", "күштерді көрсет", "күштер диаграм", "ауырлық күші", "тірек реакция", "үйкеліс күші", "ньютон заң")),
        ("momentum_collision", ("импульс", "соқтығыс", "серпімді соқтығыс", "серпімсіз соқтығыс")),
        ("pressure_buoyancy", ("архимед", "көтеруші күш", "жүзу шарты", "сұйықта жүз", "батырылған дене")),
        ("fluid_pressure", ("гидростатикалық қысым", "сұйық қысымы", "паскаль заңы", "қатынас ыдыс")),
        ("heat_transfer", ("жылу алмас", "жылу бері", "жылу өткізгіш", "конвекц", "сәулелен", "жылу шығыны", "салқындау")),
        ("phase_change", ("балқу", "қатаю", "булану", "қайнау", "конденсац", "агрегаттық күй", "фазалық ауыс")),
        ("gas_process", ("изотерм", "изобар", "изохор", "газ заңы", "идеал газ", "поршень", "p-v", "pv")),
        ("spring", ("серіппе", "гук заңы", "қатаңдық коэффициент")),
        ("oscillation", ("маятник", "гармоникалық тербел", "тербеліс периоды")),
        ("wave", ("толқын ұзындығы", "механикалық толқын", "дыбыс толқыны", "көлденең толқын", "бойлық толқын", "интерференц", "дифракц")),
        ("lens", ("линза", "фокус аралығы", "оптикалық күш", "жинағыш линза", "шашыратқыш линза")),
        ("mirror", ("айна", "сфералық айна", "жазық айна")),
        ("ray_optics", ("шағылу заңы", "сыну заңы", "снелл", "түсу бұрышы", "сыну бұрышы", "жарық сәулесі")),
        ("electric_circuit", ("электр тізбек", "амперметр", "вольтметр", "резистор", "реостат", "ом заңы", "тізбектей жалға", "параллель жалға")),
        ("electric_field", ("электр өрісі", "өріс кернеулігі", "кулон заңы", "зарядтар", "электр күш сызық")),
        ("electromagnetic_induction", ("электромагниттік индукц", "фарадей", "ленц ереж", "индукциялық ток", "магнит ағыны")),
        ("magnetic_field", ("магнит өрісі", "магнит индукция", "ампер күші", "лоренц күші", "сол қол ереж", "магнит күш сызық")),
        ("lever", ("иіндік", "күш моменті", "моменттер ережесі", "тірек нүктесі")),
        ("pulley", ("блок жүйесі", "қозғалмалы блок", "қозғалмайтын блок", "полиспаст")),
        ("measurement", ("бөлік құны", "өлшеу қателігі", "шкала", "сызғыш", "динамометр", "мензурка", "термометр")),
        ("energy_conversion", ("энергия түрлен", "потенциалдық энергия", "кинетикалық энергия", "механикалық энергияның сақтал")),
        ("linear_motion", ("түзу сызықты", "бірқалыпты қозғалыс", "жылдамдық тұрақты", "s=vt", "s = vt")),
    ]
    for kind, needles in rules:
        if any(n in low for n in needles):
            return kind
    return "generic_physics_scene"


def infer_visual_family(text: str) -> str:
    low = _low(text)
    if any(k in low for k in ("кесте", "таблица", "деректер кестесі")):
        return "table"
    if any(k in low for k in ("график", "тәуелділік графигі", "диаграмма", "chart", "plot")):
        return "graph"
    if any(k in low for k in ("фото", "фотосурет", "реалистік сурет", "иллюстрация")):
        return "image"
    if any(k in low for k in ("сызба", "схема", "вектор", "траектория", "суретпен сал", "күштерді сал", "сәулелерді сал", "тізбекті сал")):
        return "diagram"
    return "none"


def _extract_rotating_points(context: str) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for label, value in re.findall(r"(?iu)\b([A-ZА-Я])\s*нүктесі.{0,100}?(\d+(?:[,.]\d+)?)\s*м\b", context):
        try:
            r = float(value.replace(",", "."))
        except ValueError:
            continue
        if r > 0:
            points.append({"label": label.upper(), "radius_m": r})
    return points[:4]


def _extract_measurement_value(context: str, names: tuple[str, ...]) -> float | None:
    low = _low(context)
    for name in names:
        m = re.search(re.escape(name) + r"[^\d]{0,30}(\d+(?:[,.]\d+)?)", low)
        if m:
            try:
                return float(m.group(1).replace(",", "."))
            except ValueError:
                pass
    return None


def default_spec(kind: str, context: str = "") -> dict[str, Any]:
    kind = kind if kind in DIAGRAM_TYPES else "generic_physics_scene"
    base: dict[str, Any] = {"diagram_type": kind, "axes": {"show": kind in AXIS_DIAGRAM_TYPES}}
    if kind == "rotating_platform":
        pts = _extract_rotating_points(context)
        base.update({"points": pts or [{"label": "A", "radius_m": 0.8}, {"label": "B", "radius_m": 0.4}], "direction": "clockwise" if "сағат тілі" in _low(context) else "counterclockwise"})
    elif kind == "projectile_motion":
        base.update({"v0": _extract_measurement_value(context, ("бастапқы жылдамдық", "v0")), "angle_deg": _extract_measurement_value(context, ("бұрыш", "alpha", "α"))})
    elif kind == "inclined_plane":
        base.update({"angle_deg": _extract_measurement_value(context, ("көлбеу бұрышы", "бұрыш", "alpha", "α")) or 30})
    return base


def validate_diagram_spec(spec: Any, context: str = "", title: str = "") -> ValidationResult:
    source = dict(spec) if isinstance(spec, dict) else {}
    combined = " ".join((context, title, str(source.get("caption") or ""), str(source.get("title") or "")))
    inferred = infer_diagram_type(combined)
    requested = str(source.get("diagram_type") or source.get("kind") or "").strip().lower()
    errors: list[str] = []
    repaired = False

    if requested not in DIAGRAM_TYPES:
        if requested:
            errors.append(f"unknown diagram_type: {requested}")
        requested = inferred
        repaired = True

    kind = requested or inferred
    if inferred != "generic_physics_scene" and kind != inferred:
        # Strong semantic evidence wins over a mismatched model guess.
        errors.append(f"topic mismatch: {kind} -> {inferred}")
        kind = inferred
        repaired = True

    if kind not in DIAGRAM_TYPES:
        kind = "generic_physics_scene"
        repaired = True

    out = default_spec(kind, combined)
    # Only copy safe structured fields. Never copy raw markup.
    for key in ("caption", "direction", "points", "vectors", "objects", "trajectory", "axes", "angle_deg", "v0", "medium1", "medium2", "focal_length", "circuit", "charges", "values"):
        if key in source and source[key] is not None:
            out[key] = source[key]

    out["diagram_type"] = kind
    if not isinstance(out.get("axes"), dict):
        out["axes"] = {"show": False}
    if kind not in AXIS_DIAGRAM_TYPES:
        if out.get("axes", {}).get("show"):
            repaired = True
        out["axes"] = {"show": False}

    # Semantic templates own geometry; unrelated model leftovers are removed.
    if kind in SEMANTIC_TEMPLATE_TYPES:
        keep_points = kind in {"rotating_platform"}
        for key in ("trajectory", "vectors", "objects"):
            if key in out and out.get(key):
                out.pop(key, None)
                repaired = True
        if not keep_points:
            out.pop("points", None)
        elif kind == "rotating_platform":
            pts = _extract_rotating_points(combined)
            if len(pts) >= 2:
                out["points"] = pts
            elif not isinstance(out.get("points"), list) or len(out.get("points") or []) < 2:
                out["points"] = [{"label": "A", "radius_m": 0.8}, {"label": "B", "radius_m": 0.4}]

    # Generic scenes may use only a constrained primitive vocabulary.
    if kind == "generic_physics_scene":
        allowed_obj = {"block", "box", "circle", "ground", "line", "text", "spring", "lens", "mirror", "battery", "resistor", "switch", "coil", "magnet", "pulley", "fulcrum"}
        objects = []
        for obj in out.get("objects") or []:
            if isinstance(obj, dict) and str(obj.get("type") or "").lower() in allowed_obj:
                objects.append(obj)
        out["objects"] = objects[:20]
        out["vectors"] = [v for v in (out.get("vectors") or []) if isinstance(v, dict)][:16]
        out["points"] = [p for p in (out.get("points") or []) if isinstance(p, dict)][:20]
        out["trajectory"] = list(out.get("trajectory") or [])[:40]

    confidence = 0.97 if inferred != "generic_physics_scene" else (0.82 if requested and requested != "generic_physics_scene" else 0.68)
    return ValidationResult(out, confidence, errors, repaired)


def diagram_prompt_contract(context: str = "") -> str:
    recommendation = infer_diagram_type(context)
    types = ", ".join(sorted(DIAGRAM_TYPES))
    return f"""
Физикалық көрнекілікті RAW SVG/HTML емес, тек құрылымдық JSON ретінде сипатта.
Ұсынылған diagram_type: {recommendation}.
Рұқсат етілген diagram_type: {types}.
Координаталар тек generic_physics_scene үшін 0..100 шкаласында беріледі (x оңға, y жоғары).
Арнайы типтерде геометрияны өзің ойлап салма: тек физикалық мәндер мен қажет қысқа label/caption бер; renderer геометрияны өзі құрады.
Суреттің ішіне ұзақ түсіндірме қоспа. Толық түсіндірмені explanation өрісіне қазақ тілінде 2–5 сөйлеммен жаз.
Координата осін тек projectile_motion үшін немесе тапсырма шынымен координата осін талап етсе қолдан.
Физикалық мағынасыз сәндік нүкте, жалған вектор, ASCII art, SVG, HTML, XML қоспа.
JSON форматы:
{{"title":"...","explanation":"Сызбаның физикалық мағынасын 2–5 сөйлеммен түсіндір.","diagram":{{"diagram_type":"{recommendation}","caption":"қысқа семантикалық белгі","points":[],"vectors":[],"objects":[]}}}}
""".strip()


def render_chart_svg(spec: Any, title: str = "График") -> bytes:
    """Small dependency-free SVG chart renderer for generated chat artifacts."""
    data = dict(spec) if isinstance(spec, dict) else {}
    kind = str(data.get("type") or data.get("kind") or "line").lower()
    if kind not in {"line", "bar"}:
        kind = "line"
    x = data.get("x") if isinstance(data.get("x"), list) else []
    y = data.get("y") if isinstance(data.get("y"), list) else []
    n = min(len(x), len(y), 30)
    x, y = x[:n], y[:n]
    nums: list[float] = []
    for v in y:
        try:
            f = float(v)
        except (TypeError, ValueError):
            f = 0.0
        nums.append(f if math.isfinite(f) else 0.0)
    if not nums:
        x, nums = [0, 1, 2], [0.0, 1.0, 2.0]
    width, height = 1200, 720
    l, r, t, b = 120, 70, 100, 100
    plot_w, plot_h = width-l-r, height-t-b
    ymin, ymax = min(nums), max(nums)
    if math.isclose(ymin, ymax):
        ymin -= 1.0; ymax += 1.0
    def sy(v: float) -> float:
        return t + (ymax-v)/(ymax-ymin)*plot_h
    def sx(i: int) -> float:
        return l + (i/(max(1, len(nums)-1)))*plot_w
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>']
    parts.append(f'<text x="600" y="48" text-anchor="middle" font-family="Times New Roman" font-size="32" font-weight="700">{escape(title)}</text>')
    parts.append(f'<line x1="{l}" y1="{t+plot_h}" x2="{l+plot_w}" y2="{t+plot_h}" stroke="#52667d" stroke-width="3"/>')
    parts.append(f'<line x1="{l}" y1="{t}" x2="{l}" y2="{t+plot_h}" stroke="#52667d" stroke-width="3"/>')
    for j in range(5):
        val = ymin + (ymax-ymin)*j/4
        yy = sy(val)
        parts.append(f'<line x1="{l}" y1="{yy:.1f}" x2="{l+plot_w}" y2="{yy:.1f}" stroke="#e3eaf2" stroke-width="1"/>')
        parts.append(f'<text x="{l-14}" y="{yy+7:.1f}" text-anchor="end" font-family="Times New Roman" font-size="20">{val:.3g}</text>')
    if kind == "bar":
        bw = plot_w/max(1, len(nums))*0.58
        zero = sy(0) if ymin <= 0 <= ymax else sy(ymin)
        for i, v in enumerate(nums):
            xx = l + (i+0.5)/len(nums)*plot_w
            yy = sy(v)
            top = min(yy, zero); h = abs(zero-yy)
            parts.append(f'<rect x="{xx-bw/2:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{max(2,h):.1f}" fill="#dceafe" stroke="#1769ff" stroke-width="2"/>')
    else:
        pts = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i,v in enumerate(nums))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="#1769ff" stroke-width="5"/>')
        for i,v in enumerate(nums):
            parts.append(f'<circle cx="{sx(i):.1f}" cy="{sy(v):.1f}" r="6" fill="#1769ff"/>')
    labels = x if len(x)==len(nums) else list(range(len(nums)))
    for i,label in enumerate(labels):
        xx = sx(i) if kind == "line" else l + (i+0.5)/len(nums)*plot_w
        parts.append(f'<text x="{xx:.1f}" y="{t+plot_h+34}" text-anchor="middle" font-family="Times New Roman" font-size="19">{escape(str(label))}</text>')
    parts.append(f'<text x="{l+plot_w/2}" y="{height-28}" text-anchor="middle" font-family="Times New Roman" font-size="23">{escape(str(data.get("x_label") or "x"))}</text>')
    parts.append(f'<text x="30" y="{t+plot_h/2}" transform="rotate(-90 30 {t+plot_h/2})" text-anchor="middle" font-family="Times New Roman" font-size="23">{escape(str(data.get("y_label") or "y"))}</text>')
    parts.append('</svg>')
    return ''.join(parts).encode('utf-8')
