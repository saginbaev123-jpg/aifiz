from __future__ import annotations

"""Deterministic textbook-style SVG diagrams for school physics.

The model supplies a small structured spec. This renderer owns geometry and text,
so the UI never depends on an image model drawing equations, arrows or labels.
Coordinates for generic diagrams use 0..100 with x rightward and y upward.
"""

from html import escape
import math
import re
import textwrap
from typing import Any

from .visual_engine import infer_diagram_type as _infer_visual_diagram_type, validate_diagram_spec

WIDTH = 1200
HEIGHT = 720
MARGIN_X = 72
MARGIN_Y = 72


def _num(value: Any, default: float = 0.0, lo: float = -200.0, hi: float = 200.0) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(value):
        return default
    return max(lo, min(hi, value))


def _xy(x: Any, y: Any) -> tuple[float, float]:
    nx = _num(x, 50.0, 0.0, 100.0)
    ny = _num(y, 50.0, 0.0, 100.0)
    sx = MARGIN_X + nx / 100.0 * (WIDTH - 2 * MARGIN_X)
    sy = HEIGHT - MARGIN_Y - ny / 100.0 * (HEIGHT - 2 * MARGIN_Y)
    return sx, sy


def _label(value: Any) -> str:
    s = str(value or "").strip().replace("$", "")
    s = re.sub(r"\\vec\{([^{}]+)\}", r"\1⃗", s)
    s = re.sub(r"\\mathrm\{([^{}]+)\}", r"\1", s)
    s = re.sub(r"\\text\{([^{}]+)\}", r"\1", s)
    replacements = {
        r"\theta": "θ", r"\alpha": "α", r"\beta": "β", r"\gamma": "γ",
        r"\Delta": "Δ", r"\lambda": "λ", r"\omega": "ω", r"\mu": "μ",
        r"\rho": "ρ", r"\varphi": "φ", r"\phi": "φ", r"\degree": "°",
        r"\cdot": "·", r"\times": "×", r"\rightarrow": "→", r"\leftarrow": "←",
    }
    for src, dst in replacements.items():
        s = s.replace(src, dst)
    subs = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")
    sup = str.maketrans("0123456789+-=()", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾")
    s = re.sub(r"_\{?([0-9]+)\}?", lambda m: m.group(1).translate(subs), s)
    s = re.sub(r"\^\{?([0-9]+)\}?", lambda m: m.group(1).translate(sup), s)
    for raw, uni in {"_p": "ₚ", "_k": "ₖ", "_x": "ₓ", "_y": "ᵧ", "_n": "ₙ", "_t": "ₜ", "_c": "c"}.items():
        s = s.replace(raw, uni)
    s = s.replace("{", "").replace("}", "")
    return escape(s)


def _path(points: list[Any]) -> str:
    coords: list[tuple[float, float]] = []
    for p in points:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            coords.append(_xy(p[0], p[1]))
        elif isinstance(p, dict):
            coords.append(_xy(p.get("x"), p.get("y")))
    if len(coords) < 2:
        return ""
    return "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in coords)


def _svg_text(x: float, y: float, text: Any, *, size: int = 24, anchor: str = "middle", weight: int = 400, italic: bool = False, fill: str = "#10213d") -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    lines = value.split("\n")
    line_h = size * 1.2
    start = y - (len(lines) - 1) * line_h / 2
    spans = []
    for i, line in enumerate(lines):
        spans.append(f'<tspan x="{x:.1f}" y="{start + i*line_h:.1f}">{_label(line)}</tspan>')
    style = ' font-style="italic"' if italic else ""
    return f'<text text-anchor="{anchor}" font-family="Times New Roman,serif" font-size="{size}" font-weight="{weight}" fill="{fill}"{style}>{"".join(spans)}</text>'


def _base(title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{_label(title)}">',
        '<defs>',
        '<marker id="arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L12,6 L0,12 z" fill="#123b6d"/></marker>',
        '<marker id="heatArrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L12,6 L0,12 z" fill="#c44a2d"/></marker>',
        '<marker id="axisArrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#5b6f89"/></marker>',
        '</defs>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        _svg_text(WIDTH/2, 42, title, size=30, weight=700),
    ]


def _finish(parts: list[str], caption: str = "") -> bytes:
    """Finish the SVG with diagram graphics only.

    Explanatory prose must stay outside the image and be rendered by the chat/UI.
    ``caption`` is intentionally ignored here; it remains available in the structured
    diagram spec for validation and textual explanation.
    """
    parts.append("</svg>")
    return "".join(parts).encode("utf-8")



def infer_diagram_type(text: str) -> str:
    return _infer_visual_diagram_type(text)

def _default_spec(diagram_type: str, title: str = "") -> dict[str, Any]:
    kind = (diagram_type or "generic").lower()
    if kind in {"motion", "motion_vectors", "curvilinear_motion"}:
        return {
            "diagram_type": "motion_vectors",
            "axes": {"show": False},
            "trajectory": [[17, 25], [27, 34], [39, 43], [52, 50], [66, 55]],
            "points": [{"x": 39, "y": 43, "label": "A", "radius": 1.2}],
            "vectors": [
                {"x": 39, "y": 43, "dx": 20, "dy": 8, "label": "v"},
                {"x": 39, "y": 43, "dx": -8, "dy": -16, "label": "a"},
            ],
        }
    if kind in {"projectile", "projectile_motion"}:
        return {
            "diagram_type": "projectile_motion",
            "axes": {"show": True, "origin": [12, 12], "x_label": "x", "y_label": "y"},
            "trajectory": [[12, 15], [25, 34], [40, 47], [56, 53], [72, 49], [88, 34]],
            "vectors": [
                {"x": 12, "y": 15, "dx": 17, "dy": 17, "label": "v₀"},
                {"x": 56, "y": 53, "dx": 17, "dy": 0, "label": "v"},
                {"x": 56, "y": 53, "dx": 0, "dy": -17, "label": "g"},
            ],
        }
    if kind in {"force", "forces", "free_body"}:
        return {
            "diagram_type": "forces",
            "axes": {"show": False},
            "objects": [{"type": "block", "x": 50, "y": 38, "w": 18, "h": 12, "label": "m"}, {"type": "ground", "y": 32}],
            "vectors": [
                {"x": 50, "y": 44, "dx": 0, "dy": 22, "label": "N"},
                {"x": 50, "y": 38, "dx": 0, "dy": -22, "label": "mg"},
                {"x": 59, "y": 38, "dx": 20, "dy": 0, "label": "F"},
            ],
        }
    if kind in {"energy", "energy_conversion"}:
        return {
            "diagram_type": "energy_conversion",
            "axes": {"show": False},
            "objects": [
                {"type": "box", "x": 27, "y": 50, "w": 30, "h": 18, "label": "Потенциалдық энергия\nEₚ көп"},
                {"type": "box", "x": 73, "y": 50, "w": 30, "h": 18, "label": "Кинетикалық энергия\nEₖ көп"},
            ],
            "vectors": [{"x": 43, "y": 50, "dx": 14, "dy": 0, "label": "түрлену"}],
        }
    if kind in {"heat", "heat_transfer", "thermal", "thermal_transfer", "conduction_convection_radiation"}:
        return {"diagram_type": "heat_transfer", "axes": {"show": False}, "caption": "Жылу ыстық денеден салқынырақ ортаға беріледі."}
    if kind in {"rotating_platform", "turntable", "rotating_disk", "angular_velocity"}:
        return {
            "diagram_type": "rotating_platform",
            "axes": {"show": False},
            "direction": "clockwise",
            "points": [
                {"label": "A", "radius_m": 0.80},
                {"label": "B", "radius_m": 0.40},
            ],
            "caption": "Бұрыштық жылдамдық бірдей болғанда v = ωr, сондықтан осьтен алыс нүктенің сызықтық жылдамдығы үлкен."
        }
    if kind in {"circular", "circular_motion", "centripetal", "centripetal_acceleration"}:
        return {"diagram_type": "circular_motion", "axes": {"show": False}, "caption": "Жылдамдық жанама бойымен, центрге тартқыш үдеу шеңбер центріне қарай бағытталады."}
    if kind in {"linear", "linear_motion", "uniform_motion"}:
        return {"diagram_type": "linear_motion", "axes": {"show": False}}
    return {"diagram_type": "generic", "axes": {"show": False}, "objects": [{"type": "text", "x": 50, "y": 50, "label": title or "Физикалық сызба"}]}


def normalize_diagram_spec(spec: Any, title: str = "") -> dict[str, Any]:
    """Validate/repair a model spec through the universal visual engine."""
    context = " ".join([title, str(spec.get("caption") or "") if isinstance(spec, dict) else ""])
    return validate_diagram_spec(spec, context=context, title=title).spec

def _render_heat_transfer(spec: dict[str, Any], title: str) -> bytes:
    parts = _base(title)
    # Cup and liquid
    parts += [
        '<path d="M430 300 L455 540 Q465 590 520 590 L680 590 Q735 590 745 540 L770 300 Z" fill="#eef5ff" stroke="#24496f" stroke-width="5"/>',
        '<path d="M458 335 L742 335" stroke="#d56b45" stroke-width="16" stroke-linecap="round"/>',
        '<path d="M770 370 C870 360 875 515 770 500" fill="none" stroke="#24496f" stroke-width="18"/>',
        '<path d="M770 390 C835 390 835 480 770 475" fill="none" stroke="#ffffff" stroke-width="9"/>',
        _svg_text(600, 470, "Ыстық сұйық", size=27, weight=700),
    ]
    # Convection / steam upwards
    for x in (545, 600, 655):
        parts.append(f'<path d="M{x} 300 C{x-20} 260 {x+22} 235 {x} 195 C{x-20} 160 {x+20} 135 {x} 105" fill="none" stroke="#c44a2d" stroke-width="5" marker-end="url(#heatArrow)"/>')
    parts.append(_svg_text(825, 122, "Конвекция", size=25, anchor="start", weight=700, fill="#8c351f"))
    parts.append(_svg_text(825, 154, "жылы ауа жоғары көтеріледі", size=21, anchor="start", fill="#5b6f89"))
    # Radiation left-up
    for off in (0, 24, 48):
        parts.append(f'<line x1="440" y1="{330+off}" x2="{245-off/2:.0f}" y2="{235+off:.0f}" stroke="#c44a2d" stroke-width="4" marker-end="url(#heatArrow)"/>')
    parts.append(_svg_text(235, 205, "Сәулелену", size=25, weight=700, fill="#8c351f"))
    parts.append(_svg_text(235, 232, "энергия электромагниттік\nтолқындар арқылы тарайды", size=20, fill="#5b6f89"))
    # Conduction right through wall/handle
    parts.append('<line x1="744" y1="505" x2="940" y2="505" stroke="#c44a2d" stroke-width="5" marker-end="url(#heatArrow)"/>')
    parts.append(_svg_text(955, 455, "Жылу өткізгіштік", size=25, weight=700, fill="#8c351f"))
    parts.append(_svg_text(955, 485, "ыдыс қабырғасы арқылы", size=20, fill="#5b6f89"))
    caption = str(spec.get("caption") or "Жылу ыстық денеден салқынырақ ортаға беріледі.")
    return _finish(parts, caption)



def _render_rotating_platform(spec: dict[str, Any], title: str) -> bytes:
    parts = _base(title)
    cx, cy, radius = 575, 395, 225
    parts += [
        f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="#f8fbff" stroke="#1769ff" stroke-width="5"/>',
        f'<circle cx="{cx}" cy="{cy}" r="7" fill="#071c36"/>',
        _svg_text(cx-22, cy+34, "O", size=25, weight=700),
        _svg_text(cx, 105, "айналмалы платформа", size=24, weight=700),
    ]

    raw_points = spec.get("points") if isinstance(spec.get("points"), list) else []
    values = []
    for item in raw_points:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        try:
            r_m = float(item.get("radius_m"))
        except (TypeError, ValueError):
            continue
        if label and r_m > 0:
            values.append((label, r_m))
    if len(values) < 2:
        values = [("A", 0.80), ("B", 0.40)]
    max_r = max(v for _, v in values) or 1.0

    # Put both points on the same radius so their distances from the axis are immediately comparable.
    angle = math.radians(18)
    point_coords = []
    for label, r_m in values[:3]:
        rr = radius * (r_m / max_r)
        px = cx + rr * math.cos(angle)
        py = cy - rr * math.sin(angle)
        point_coords.append((label, r_m, px, py, rr))
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{px:.1f}" y2="{py:.1f}" stroke="#9aa9bb" stroke-width="2.5" stroke-dasharray="8 7"/>')
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="11" fill="#1769ff" stroke="#0b4ea2" stroke-width="3"/>')
        parts.append(_svg_text(px+20, py-16, f"{label}  r={r_m:g} м", size=23, anchor="start", weight=700))

    # Tangential velocities: arrow lengths are proportional to radius because v = ωr.
    for label, r_m, px, py, rr in point_coords:
        tx, ty = -math.sin(angle), -math.cos(angle)
        vlen = 95 + 95 * (r_m / max_r)
        vx, vy = px + tx*vlen, py + ty*vlen
        parts.append(f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{vx:.1f}" y2="{vy:.1f}" stroke="#123b6d" stroke-width="5" marker-end="url(#arrow)"/>')
        parts.append(_svg_text((px+vx)/2+14, (py+vy)/2-10, f"v{label}", size=25, weight=700, italic=True))

    # Rotation direction and core relation.
    direction = str(spec.get("direction") or "clockwise").lower()
    if direction in {"clockwise", "cw", "сағат тілі", "сағат тілі бағытымен"}:
        arc = f'M {cx-105} {cy-205} A 235 235 0 0 1 {cx+135} {cy-190}'
    else:
        arc = f'M {cx+135} {cy-190} A 235 235 0 0 0 {cx-105} {cy-205}'
    parts.append(f'<path d="{arc}" fill="none" stroke="#c44a2d" stroke-width="5" marker-end="url(#heatArrow)"/>')
    parts.append(_svg_text(cx+10, cy-245, "ω", size=30, weight=700, italic=True, fill="#8c351f"))
    parts.append(_svg_text(915, 265, "Барлық нүктеде ω бірдей", size=24, anchor="start", weight=700))
    parts.append(_svg_text(915, 305, "v = ωr", size=28, anchor="start", weight=700, italic=True, fill="#123b6d"))
    if len(point_coords) >= 2:
        # Determine outer/inner labels by radius rather than by fixed A/B naming.
        ordered = sorted(point_coords, key=lambda t: t[1], reverse=True)
        parts.append(_svg_text(915, 350, f"r{ordered[0][0]} > r{ordered[1][0]}, сондықтан v{ordered[0][0]} > v{ordered[1][0]}", size=24, anchor="start"))
    caption = str(spec.get("caption") or "Осьтен қашықтық артқан сайын сызықтық жылдамдық артады, ал бұрыштық жылдамдық өзгермейді.")
    return _finish(parts, caption)

def _render_circular_motion(spec: dict[str, Any], title: str) -> bytes:
    parts = _base(title)
    cx, cy, r = 560, 390, 205
    angle = math.radians(35)
    px = cx + r * math.cos(angle)
    py = cy - r * math.sin(angle)
    # Circle, center and radius
    parts += [
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#f8fbff" stroke="#1769ff" stroke-width="5"/>',
        f'<circle cx="{cx}" cy="{cy}" r="7" fill="#071c36"/>',
        f'<line x1="{cx}" y1="{cy}" x2="{px:.1f}" y2="{py:.1f}" stroke="#8294aa" stroke-width="3" stroke-dasharray="8 7"/>',
        f'<circle cx="{px:.1f}" cy="{py:.1f}" r="13" fill="#1769ff" stroke="#0b4ea2" stroke-width="3"/>',
        _svg_text(cx-20, cy+34, "O", size=25, weight=700),
        _svg_text((cx+px)/2-10, (cy+py)/2+25, "R", size=24, italic=True),
    ]
    # Tangent direction at point: rotate radius +90 degrees in screen coords.
    tx, ty = -math.sin(angle), -math.cos(angle)
    vlen = 185
    vx, vy = px + tx*vlen, py + ty*vlen
    parts.append(f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{vx:.1f}" y2="{vy:.1f}" stroke="#123b6d" stroke-width="6" marker-end="url(#arrow)"/>')
    parts.append(_svg_text((px+vx)/2+20, (py+vy)/2-12, "v", size=27, weight=700, italic=True))
    # Centripetal acceleration points from body to center.
    ax = px + (cx-px)*0.72
    ay = py + (cy-py)*0.72
    parts.append(f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{ax:.1f}" y2="{ay:.1f}" stroke="#c44a2d" stroke-width="6" marker-end="url(#heatArrow)"/>')
    parts.append(_svg_text((px+ax)/2+8, (py+ay)/2-18, "aц", size=27, weight=700, italic=True, fill="#8c351f"))
    parts.append(_svg_text(915, 310, "v — траекторияға жанама", size=23, anchor="start"))
    parts.append(_svg_text(915, 350, "aц — центрге қарай", size=23, anchor="start", fill="#8c351f"))
    caption = str(spec.get("caption") or "Жылдамдық жанама бойымен, центрге тартқыш үдеу шеңбер центріне қарай бағытталады.")
    return _finish(parts, caption)


def _render_linear_motion(spec: dict[str, Any], title: str) -> bytes:
    parts = _base(title)
    parts += [
        '<line x1="160" y1="520" x2="1040" y2="520" stroke="#52667d" stroke-width="4"/>',
        '<rect x="470" y="390" width="220" height="115" rx="18" fill="#eaf3ff" stroke="#1769ff" stroke-width="5"/>',
        '<circle cx="515" cy="520" r="24" fill="#24496f"/><circle cx="645" cy="520" r="24" fill="#24496f"/>',
        '<line x1="690" y1="445" x2="930" y2="445" stroke="#123b6d" stroke-width="6" marker-end="url(#arrow)"/>',
        _svg_text(815, 410, "v", size=28, weight=700, italic=True),
        _svg_text(580, 445, "дене", size=26, weight=700),
    ]
    return _finish(parts, str(spec.get("caption") or "Қозғалыс бағыты жылдамдық векторымен көрсетілген."))




def _render_projectile_motion(spec: dict[str, Any], title: str) -> bytes:
    parts = _base(title)
    ox, oy = 160, 585
    parts += [
        f'<line x1="{ox}" y1="{oy}" x2="1080" y2="{oy}" stroke="#5b6f89" stroke-width="3" marker-end="url(#axisArrow)"/>',
        f'<line x1="{ox}" y1="{oy}" x2="{ox}" y2="105" stroke="#5b6f89" stroke-width="3" marker-end="url(#axisArrow)"/>',
        _svg_text(1090, oy+30, "x", size=24), _svg_text(ox+24, 112, "y", size=24),
    ]
    # textbook-style parabolic trajectory
    pts=[]
    for i in range(31):
        t=i/30
        x=ox + 760*t
        y=oy - (420*(4*t*(1-t)))
        pts.append((x,y))
    d='M ' + ' L '.join(f'{x:.1f} {y:.1f}' for x,y in pts)
    parts.append(f'<path d="{d}" fill="none" stroke="#1769ff" stroke-width="5"/>')
    angle=float(spec.get('angle_deg') or 40)
    angle=max(15,min(75,angle))
    a=math.radians(angle)
    vx=ox+165*math.cos(a); vy=oy-165*math.sin(a)
    parts.append(f'<line x1="{ox}" y1="{oy}" x2="{vx:.1f}" y2="{vy:.1f}" stroke="#123b6d" stroke-width="6" marker-end="url(#arrow)"/>')
    parts.append(_svg_text((ox+vx)/2, (oy+vy)/2-18, "v₀", size=27, weight=700, italic=True))
    mx,my=pts[15]
    parts.append(f'<line x1="{mx:.1f}" y1="{my:.1f}" x2="{mx:.1f}" y2="{my+150:.1f}" stroke="#c44a2d" stroke-width="5" marker-end="url(#heatArrow)"/>')
    parts.append(_svg_text(mx+28,my+80,"g",size=26,weight=700,italic=True,fill="#8c351f"))
    return _finish(parts, str(spec.get('caption') or 'Дене горизонталь және тік қозғалыстардың қосындысы ретінде параболалық траекториямен қозғалады.'))


def _render_free_fall(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    x=570
    ys=[140,230,340,480]
    for i,y in enumerate(ys):
        r=16
        parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#1769ff"/>')
        if i < len(ys)-1:
            parts.append(f'<line x1="{x+45}" y1="{y}" x2="{x+45}" y2="{min(620,y+70+25*i)}" stroke="#123b6d" stroke-width="5" marker-end="url(#arrow)"/>')
            parts.append(_svg_text(x+85,y+45,f"v{i+1}",size=23,anchor="start",italic=True))
    parts.append(f'<line x1="{x-110}" y1="145" x2="{x-110}" y2="520" stroke="#c44a2d" stroke-width="5" marker-end="url(#heatArrow)"/>')
    parts.append(_svg_text(x-145,330,"g",size=28,weight=700,italic=True,fill="#8c351f"))
    return _finish(parts, str(spec.get('caption') or 'Еркін түсу кезінде үдеу төмен бағытталған және шамасы g-ге тең.'))


def _render_accelerated_motion(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    y=480
    xs=[180,300,455,660,920]
    for i,x in enumerate(xs):
        parts.append(f'<circle cx="{x}" cy="{y}" r="13" fill="#1769ff"/>')
        parts.append(_svg_text(x,y+38,f"t{i}",size=20))
    parts.append(f'<line x1="150" y1="{y+70}" x2="1050" y2="{y+70}" stroke="#52667d" stroke-width="3" marker-end="url(#axisArrow)"/>')
    parts.append(_svg_text(600,220,"Бірдей уақыт аралықтарындағы орындар",size=26,weight=700))
    parts.append(_svg_text(600,270,"аралықтың ұлғаюы → жылдамдық артады",size=24,fill="#5b6f89"))
    parts.append(f'<line x1="450" y1="350" x2="760" y2="350" stroke="#c44a2d" stroke-width="5" marker-end="url(#heatArrow)"/>')
    parts.append(_svg_text(610,322,"a",size=27,weight=700,italic=True,fill="#8c351f"))
    return _finish(parts, str(spec.get('caption') or 'Теңүдемелі қозғалыста бірдей уақыт аралығындағы орын ауыстырулар өзгереді.'))


def _render_forces(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    cx,cy=590,385
    parts += [
        '<line x1="200" y1="520" x2="980" y2="520" stroke="#334e68" stroke-width="5"/>',
        f'<rect x="{cx-95}" y="{cy-65}" width="190" height="130" rx="14" fill="#eaf3ff" stroke="#1769ff" stroke-width="5"/>',
        _svg_text(cx,cy,"m",size=30,weight=700,italic=True),
        f'<line x1="{cx}" y1="{cy-65}" x2="{cx}" y2="175" stroke="#123b6d" stroke-width="6" marker-end="url(#arrow)"/>',
        f'<line x1="{cx}" y1="{cy+65}" x2="{cx}" y2="585" stroke="#c44a2d" stroke-width="6" marker-end="url(#heatArrow)"/>',
        _svg_text(cx+35,210,"N",size=27,anchor="start",weight=700,italic=True),
        _svg_text(cx+35,565,"mg",size=27,anchor="start",weight=700,italic=True,fill="#8c351f"),
    ]
    return _finish(parts, str(spec.get('caption') or 'Еркін дене диаграммасында тек денеге әсер ететін күштер көрсетіледі.'))


def _render_inclined_plane(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    x1,y1,x2,y2=210,555,955,265
    parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#52667d" stroke-width="7"/>')
    bx,by=620,390
    parts.append(f'<rect x="{bx-75}" y="{by-50}" width="150" height="100" rx="12" fill="#eaf3ff" stroke="#1769ff" stroke-width="5" transform="rotate(-21 {bx} {by})"/>')
    parts.append(f'<line x1="{bx}" y1="{by}" x2="{bx}" y2="575" stroke="#c44a2d" stroke-width="6" marker-end="url(#heatArrow)"/>')
    parts.append(_svg_text(bx+25,550,"mg",size=25,anchor="start",weight=700,italic=True,fill="#8c351f"))
    parts.append(f'<line x1="{bx}" y1="{by}" x2="{bx-80}" y2="{by-205}" stroke="#123b6d" stroke-width="6" marker-end="url(#arrow)"/>')
    parts.append(_svg_text(bx-70,235,"N",size=26,weight=700,italic=True))
    parts.append(f'<line x1="{bx}" y1="{by}" x2="{bx-190}" y2="{by+74}" stroke="#123b6d" stroke-width="5" marker-end="url(#arrow)"/>')
    parts.append(_svg_text(bx-160,430,"Fүйк",size=23,weight=700,italic=True))
    return _finish(parts, str(spec.get('caption') or 'Көлбеу жазықтықта ауырлық күші тік төмен, тірек реакциясы бетке перпендикуляр бағытталады.'))


def _render_energy_conversion(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    parts += [
        '<rect x="170" y="250" width="330" height="220" rx="28" fill="#eef5ff" stroke="#1769ff" stroke-width="4"/>',
        '<rect x="700" y="250" width="330" height="220" rx="28" fill="#eef5ff" stroke="#1769ff" stroke-width="4"/>',
        _svg_text(335,320,"Потенциалдық энергия",size=27,weight=700), _svg_text(335,382,"Eₚ",size=36,weight=700,italic=True),
        _svg_text(865,320,"Кинетикалық энергия",size=27,weight=700), _svg_text(865,382,"Eₖ",size=36,weight=700,italic=True),
        '<line x1="515" y1="360" x2="680" y2="360" stroke="#123b6d" stroke-width="6" marker-end="url(#arrow)"/>',
        _svg_text(600,330,"түрлену",size=22,weight=700),
    ]
    return _finish(parts, str(spec.get('caption') or 'Энергия бір түрден екіншісіне ауысуы мүмкін, ал тұйық жүйеде толық энергия сақталады.'))


def _render_momentum_collision(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    y=430
    parts.append('<line x1="120" y1="525" x2="1080" y2="525" stroke="#52667d" stroke-width="4"/>')
    for x,label,dirn in ((340,'m₁',1),(820,'m₂',-1)):
        parts.append(f'<rect x="{x-85}" y="{y-55}" width="170" height="110" rx="14" fill="#eaf3ff" stroke="#1769ff" stroke-width="4"/>')
        parts.append(_svg_text(x,y,label,size=28,weight=700,italic=True))
        ex=x+dirn*165
        parts.append(f'<line x1="{x}" y1="{y-90}" x2="{ex}" y2="{y-90}" stroke="#123b6d" stroke-width="5" marker-end="url(#arrow)"/>')
        parts.append(_svg_text((x+ex)/2,y-120,'v₁' if dirn==1 else 'v₂',size=25,weight=700,italic=True))
    parts.append(_svg_text(600,205,"p = mv",size=31,weight=700,italic=True))
    return _finish(parts, str(spec.get('caption') or 'Соқтығыс кезінде тұйық жүйенің толық импульсі сақталады.'))


def _render_pressure_buoyancy(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    parts += ['<rect x="280" y="220" width="640" height="350" rx="12" fill="#eef8ff" stroke="#4b87b9" stroke-width="4"/>', '<line x1="280" y1="300" x2="920" y2="300" stroke="#4b87b9" stroke-width="4"/>']
    cx,cy=600,420
    parts.append(f'<rect x="{cx-75}" y="{cy-55}" width="150" height="110" rx="12" fill="#f8f2e8" stroke="#8a6b42" stroke-width="4"/>')
    parts.append(f'<line x1="{cx}" y1="{cy-55}" x2="{cx}" y2="220" stroke="#123b6d" stroke-width="6" marker-end="url(#arrow)"/>')
    parts.append(_svg_text(cx+35,250,"F_A",size=27,anchor="start",weight=700,italic=True))
    parts.append(f'<line x1="{cx}" y1="{cy+55}" x2="{cx}" y2="585" stroke="#c44a2d" stroke-width="6" marker-end="url(#heatArrow)"/>')
    parts.append(_svg_text(cx+35,555,"mg",size=27,anchor="start",weight=700,italic=True,fill="#8c351f"))
    return _finish(parts, str(spec.get('caption') or 'Архимед күші жоғары бағытталады және ығыстырылған сұйықтың салмағына тең.'))


def _render_fluid_pressure(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    parts += ['<rect x="390" y="180" width="420" height="400" rx="8" fill="#eef8ff" stroke="#4b87b9" stroke-width="4"/>','<line x1="390" y1="260" x2="810" y2="260" stroke="#4b87b9" stroke-width="4"/>']
    for y,label in ((315,'p₁'),(430,'p₂'),(540,'p₃')):
        parts.append(f'<circle cx="590" cy="{y}" r="7" fill="#1769ff"/>')
        parts.append(f'<line x1="605" y1="{y}" x2="{690 + (y-315)*0.45:.1f}" y2="{y}" stroke="#123b6d" stroke-width="5" marker-end="url(#arrow)"/>')
        parts.append(_svg_text(560,y+8,label,size=23,anchor="end",italic=True))
    parts.append(_svg_text(930,420,"p = ρgh",size=30,weight=700,italic=True))
    return _finish(parts, str(spec.get('caption') or 'Сұйықтағы қысым тереңдік артқан сайын өседі.'))


def _render_phase_change(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    stages=[('Қатты күй',230),('Балқу',470),('Сұйық күй',730),('Булану',970)]
    for label,x in stages:
        parts.append(f'<rect x="{x-105}" y="300" width="210" height="135" rx="22" fill="#eef5ff" stroke="#1769ff" stroke-width="4"/>')
        parts.append(_svg_text(x,365,label,size=24,weight=700))
    for x in (345,600,855):
        parts.append(f'<line x1="{x}" y1="368" x2="{x+95}" y2="368" stroke="#c44a2d" stroke-width="5" marker-end="url(#heatArrow)"/>')
    parts.append(_svg_text(600,205,"Q беріледі → бөлшектердің ішкі энергиясы артады",size=26,weight=700,fill="#8c351f"))
    return _finish(parts, str(spec.get('caption') or 'Фазалық ауысу кезінде берілген жылу заттың күйін өзгертуге жұмсалады.'))


def _render_gas_process(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    parts += ['<rect x="360" y="185" width="480" height="390" fill="#f7fbff" stroke="#334e68" stroke-width="5"/>','<rect x="365" y="270" width="470" height="28" fill="#9fb5c9"/>']
    for x in range(410,810,80):
        for y in (360,430,500):
            parts.append(f'<circle cx="{x}" cy="{y}" r="7" fill="#1769ff"/>')
    parts.append(f'<line x1="600" y1="270" x2="600" y2="150" stroke="#123b6d" stroke-width="6" marker-end="url(#arrow)"/>')
    parts.append(_svg_text(630,185,"F",size=25,anchor="start",italic=True))
    parts.append(_svg_text(930,370,"p, V, T",size=30,weight=700,italic=True))
    return _finish(parts, str(spec.get('caption') or 'Газ күйі қысым p, көлем V және температура T арқылы сипатталады.'))


def _render_spring(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    y=340
    parts.append('<line x1="160" y1="130" x2="160" y2="570" stroke="#334e68" stroke-width="8"/>')
    pts=[]
    x0=160
    for i in range(13):
        x=x0+35*i
        yy=y + (38 if i%2 else -38)
        if i in (0,12): yy=y
        pts.append((x,yy))
    d='M '+' L '.join(f'{x} {yy}' for x,yy in pts)
    parts.append(f'<path d="{d}" fill="none" stroke="#1769ff" stroke-width="5"/>')
    parts.append('<rect x="580" y="280" width="190" height="120" rx="16" fill="#eaf3ff" stroke="#1769ff" stroke-width="5"/>')
    parts.append(_svg_text(675,345,'m',size=30,weight=700,italic=True))
    parts.append(f'<line x1="770" y1="340" x2="980" y2="340" stroke="#c44a2d" stroke-width="6" marker-end="url(#heatArrow)"/>')
    parts.append(_svg_text(875,310,'F = kx',size=28,weight=700,italic=True,fill="#8c351f"))
    return _finish(parts, str(spec.get('caption') or 'Гук заңы бойынша серпімділік күші деформацияға пропорционал және оған қарсы бағытталған.'))


def _render_oscillation(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    pivot=(600,150); L=310
    parts.append(f'<circle cx="{pivot[0]}" cy="{pivot[1]}" r="9" fill="#071c36"/>')
    for deg,opacity in ((-28,.35),(0,1),(28,.35)):
        a=math.radians(deg)
        x=pivot[0]+L*math.sin(a); y=pivot[1]+L*math.cos(a)
        parts.append(f'<line x1="{pivot[0]}" y1="{pivot[1]}" x2="{x:.1f}" y2="{y:.1f}" stroke="#52667d" stroke-width="4" opacity="{opacity}"/>')
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="28" fill="#1769ff" opacity="{opacity}"/>')
    parts.append('<path d="M455 500 A170 170 0 0 1 745 500" fill="none" stroke="#c44a2d" stroke-width="4" marker-end="url(#heatArrow)"/>')
    parts.append(_svg_text(600,560,'A',size=27,weight=700,italic=True))
    return _finish(parts, str(spec.get('caption') or 'Тербеліс тепе-теңдік күйінің маңында қайталанады; A — амплитуда.'))


def _render_wave(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    y0=380
    parts.append(f'<line x1="120" y1="{y0}" x2="1080" y2="{y0}" stroke="#9aa9bb" stroke-width="2"/>')
    pts=[]
    for i in range(241):
        x=130+920*i/240
        y=y0-120*math.sin(2*math.pi*i/80)
        pts.append((x,y))
    d='M '+' L '.join(f'{x:.1f} {y:.1f}' for x,y in pts)
    parts.append(f'<path d="{d}" fill="none" stroke="#1769ff" stroke-width="5"/>')
    parts.append(f'<line x1="130" y1="{y0}" x2="130" y2="{y0-120}" stroke="#c44a2d" stroke-width="4" marker-end="url(#heatArrow)"/>')
    parts.append(_svg_text(105,y0-65,'A',size=26,weight=700,italic=True))
    parts.append(f'<line x1="283" y1="190" x2="590" y2="190" stroke="#123b6d" stroke-width="4" marker-end="url(#arrow)"/>')
    parts.append(_svg_text(435,160,'λ',size=30,weight=700,italic=True))
    return _finish(parts, str(spec.get('caption') or 'Толқынның негізгі сипаттамалары: амплитуда A және толқын ұзындығы λ.'))


def _render_ray_optics(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    cx,cy=600,370
    parts.append(f'<line x1="180" y1="{cy}" x2="1020" y2="{cy}" stroke="#334e68" stroke-width="5"/>')
    parts.append(f'<line x1="{cx}" y1="120" x2="{cx}" y2="610" stroke="#9aa9bb" stroke-width="3" stroke-dasharray="9 8"/>')
    parts.append(f'<line x1="300" y1="160" x2="{cx}" y2="{cy}" stroke="#1769ff" stroke-width="5" marker-end="url(#arrow)"/>')
    parts.append(f'<line x1="{cx}" y1="{cy}" x2="900" y2="160" stroke="#1769ff" stroke-width="5" marker-end="url(#arrow)"/>')
    parts.append(_svg_text(470,250,'i',size=26,weight=700,italic=True))
    parts.append(_svg_text(730,250,'r',size=26,weight=700,italic=True))
    parts.append(_svg_text(630,145,'нормаль',size=21,anchor="start",fill="#5b6f89"))
    return _finish(parts, str(spec.get('caption') or 'Шағылу заңында түсу бұрышы шағылу бұрышына тең.'))


def _render_lens(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    cy=390; lx=600
    parts.append(f'<line x1="120" y1="{cy}" x2="1080" y2="{cy}" stroke="#9aa9bb" stroke-width="3"/>')
    parts.append(f'<path d="M{lx} 135 C540 250 540 530 {lx} 645 C660 530 660 250 {lx} 135 Z" fill="#edf8ff" stroke="#1769ff" stroke-width="5"/>')
    for fx in (420,780):
        parts.append(f'<circle cx="{fx}" cy="{cy}" r="7" fill="#071c36"/>'); parts.append(_svg_text(fx,cy+34,'F',size=22))
    # object arrow
    parts.append(f'<line x1="280" y1="{cy}" x2="280" y2="190" stroke="#c44a2d" stroke-width="6" marker-end="url(#heatArrow)"/>')
    # rays
    parts.append(f'<line x1="280" y1="190" x2="{lx}" y2="190" stroke="#1769ff" stroke-width="4"/>')
    parts.append(f'<line x1="{lx}" y1="190" x2="900" y2="520" stroke="#1769ff" stroke-width="4" marker-end="url(#arrow)"/>')
    parts.append(f'<line x1="280" y1="190" x2="{lx}" y2="{cy}" stroke="#1769ff" stroke-width="4"/>')
    parts.append(f'<line x1="{lx}" y1="{cy}" x2="900" y2="520" stroke="#1769ff" stroke-width="4"/>')
    parts.append(f'<line x1="900" y1="{cy}" x2="900" y2="520" stroke="#123b6d" stroke-width="6" marker-end="url(#arrow)"/>')
    return _finish(parts, str(spec.get('caption') or 'Жинағыш линза параллель сәулелерді фокус арқылы өткізеді; орталық сәуле ауытқымай өтеді.'))


def _render_mirror(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    x=650
    parts.append(f'<line x1="{x}" y1="130" x2="{x}" y2="610" stroke="#334e68" stroke-width="8"/>')
    for y in range(150,610,35):
        parts.append(f'<line x1="{x+4}" y1="{y}" x2="{x+28}" y2="{y-20}" stroke="#9aa9bb" stroke-width="3"/>')
    cy=360
    parts.append(f'<line x1="220" y1="190" x2="{x}" y2="{cy}" stroke="#1769ff" stroke-width="5" marker-end="url(#arrow)"/>')
    parts.append(f'<line x1="{x}" y1="{cy}" x2="250" y2="560" stroke="#1769ff" stroke-width="5" marker-end="url(#arrow)"/>')
    parts.append(f'<line x1="300" y1="{cy}" x2="980" y2="{cy}" stroke="#9aa9bb" stroke-width="3" stroke-dasharray="8 8"/>')
    return _finish(parts, str(spec.get('caption') or 'Айнадағы шағылуда түскен және шағылған сәулелер нормальмен бірдей бұрыш жасайды.'))


def _render_electric_circuit(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    # closed rectangular loop with battery, resistor, ammeter and voltmeter branch
    parts += [
        '<path d="M220 240 L480 240 M720 240 L960 240 L960 520 L220 520 L220 240" fill="none" stroke="#334e68" stroke-width="5"/>',
        '<line x1="500" y1="210" x2="500" y2="270" stroke="#334e68" stroke-width="5"/>',
        '<line x1="540" y1="190" x2="540" y2="290" stroke="#334e68" stroke-width="5"/>',
        _svg_text(520,330,'Батарея',size=22),
        '<polyline points="720,240 700,220 665,260 630,220 595,260 560,240" fill="none" stroke="#1769ff" stroke-width="5"/>',
        _svg_text(640,190,'R',size=25,weight=700,italic=True),
        '<circle cx="355" cy="520" r="42" fill="white" stroke="#1769ff" stroke-width="5"/>', _svg_text(355,530,'A',size=28,weight=700),
        '<path d="M560 240 L560 390 L720 390 L720 240" fill="none" stroke="#52667d" stroke-width="4"/>',
        '<circle cx="640" cy="390" r="42" fill="white" stroke="#1769ff" stroke-width="5"/>', _svg_text(640,400,'V',size=28,weight=700),
    ]
    return _finish(parts, str(spec.get('caption') or 'Амперметр тізбекке тізбектей, вольтметр өлшенетін элементке параллель қосылады.'))


def _render_electric_field(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    charges=[(390,380,'+'),(810,380,'−')]
    for x,y,label in charges:
        parts.append(f'<circle cx="{x}" cy="{y}" r="42" fill="#eef5ff" stroke="#1769ff" stroke-width="5"/>'); parts.append(_svg_text(x,y+10,label,size=38,weight=700))
    for off in (-120,-60,0,60,120):
        y=380+off
        parts.append(f'<path d="M440 {y} C560 {y-35 if off else y} 640 {y+35 if off else y} 760 {y}" fill="none" stroke="#123b6d" stroke-width="3.5" marker-end="url(#arrow)"/>')
    return _finish(parts, str(spec.get('caption') or 'Электр өрісінің күш сызықтары оң зарядтан шығып, теріс зарядқа бағытталады.'))


def _render_magnetic_field(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    parts += ['<rect x="430" y="315" width="170" height="130" fill="#eef5ff" stroke="#1769ff" stroke-width="4"/>','<rect x="600" y="315" width="170" height="130" fill="#fff0ec" stroke="#c44a2d" stroke-width="4"/>']
    parts.append(_svg_text(515,390,'N',size=34,weight=700)); parts.append(_svg_text(685,390,'S',size=34,weight=700))
    for dy in (-125,-75,75,125):
        parts.append(f'<path d="M470 {380+dy/2:.0f} C330 {220+dy:.0f} 870 {220+dy:.0f} 730 {380+dy/2:.0f}" fill="none" stroke="#123b6d" stroke-width="3.5" marker-end="url(#arrow)"/>')
    return _finish(parts, str(spec.get('caption') or 'Магнит өрісінің сыртқы күш сызықтары N полюсінен S полюсіне бағытталады.'))


def _render_induction(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    parts += ['<rect x="190" y="315" width="240" height="120" fill="#eef5ff" stroke="#1769ff" stroke-width="4"/>']
    parts.append(_svg_text(250,388,'N',size=34,weight=700)); parts.append(_svg_text(370,388,'S',size=34,weight=700))
    for i in range(7):
        x=620+i*35
        parts.append(f'<ellipse cx="{x}" cy="375" rx="24" ry="105" fill="none" stroke="#c44a2d" stroke-width="4"/>')
    parts.append(f'<line x1="430" y1="375" x2="560" y2="375" stroke="#123b6d" stroke-width="6" marker-end="url(#arrow)"/>')
    parts.append(_svg_text(495,340,'v',size=27,weight=700,italic=True))
    parts.append(_svg_text(775,555,'индукциялық ток',size=24,weight=700))
    return _finish(parts, str(spec.get('caption') or 'Магнит ағыны өзгергенде контурда индукциялық ток пайда болады.'))


def _render_lever(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    parts += ['<line x1="180" y1="360" x2="1020" y2="360" stroke="#334e68" stroke-width="9"/>','<path d="M560 520 L640 520 L600 360 Z" fill="#dfe8f4" stroke="#52667d" stroke-width="4"/>']
    parts.append(f'<line x1="300" y1="250" x2="300" y2="350" stroke="#c44a2d" stroke-width="6" marker-end="url(#heatArrow)"/>')
    parts.append(_svg_text(270,235,'F₁',size=26,weight=700,italic=True))
    parts.append(f'<line x1="900" y1="470" x2="900" y2="370" stroke="#123b6d" stroke-width="6" marker-end="url(#arrow)"/>')
    parts.append(_svg_text(930,470,'F₂',size=26,weight=700,italic=True))
    parts.append(_svg_text(600,585,'F₁l₁ = F₂l₂',size=30,weight=700,italic=True))
    return _finish(parts, str(spec.get('caption') or 'Иіндік тепе-теңдікте болғанда күш моменттері тең болады.'))


def _render_pulley(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    cx,cy=600,235
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="85" fill="#f8fbff" stroke="#1769ff" stroke-width="5"/>')
    parts.append(f'<line x1="{cx-85}" y1="{cy}" x2="{cx-85}" y2="545" stroke="#334e68" stroke-width="5"/>')
    parts.append(f'<line x1="{cx+85}" y1="{cy}" x2="{cx+85}" y2="500" stroke="#334e68" stroke-width="5"/>')
    parts.append(f'<rect x="{cx-145}" y="545" width="120" height="90" rx="12" fill="#eaf3ff" stroke="#1769ff" stroke-width="4"/>')
    parts.append(f'<line x1="{cx+85}" y1="500" x2="{cx+85}" y2="600" stroke="#123b6d" stroke-width="6" marker-end="url(#arrow)"/>')
    parts.append(_svg_text(cx+125,560,'F',size=27,anchor="start",weight=700,italic=True))
    return _finish(parts, str(spec.get('caption') or 'Идеал блок күштің бағытын өзгерте алады; қозғалмалы блок күштен ұтыс береді.'))


def _render_measurement(spec: dict[str, Any], title: str) -> bytes:
    parts=_base(title)
    x0,y=180,370; length=840
    parts.append(f'<rect x="{x0}" y="{y-60}" width="{length}" height="120" rx="12" fill="#fffaf0" stroke="#8a6b42" stroke-width="4"/>')
    for i in range(21):
        x=x0+length*i/20
        h=48 if i%5==0 else 30 if i%2==0 else 20
        parts.append(f'<line x1="{x:.1f}" y1="{y-60}" x2="{x:.1f}" y2="{y-60+h}" stroke="#334e68" stroke-width="3"/>')
        if i%5==0: parts.append(_svg_text(x,y+28,str(i),size=19))
    parts.append(_svg_text(600,220,'Бөлік құны = көршілес сандық белгілер айырмасы / аралық саны',size=24,weight=700))
    return _finish(parts, str(spec.get('caption') or 'Өлшеу аспабында алдымен шкаланың бөлік құны анықталады.'))

def render_physics_diagram_svg(spec: Any, title: str = "Физикалық сызба") -> bytes:
    spec = normalize_diagram_spec(spec, title)
    kind = str(spec.get("diagram_type") or "generic").lower()
    if kind == "heat_transfer":
        return _render_heat_transfer(spec, title)
    if kind == "rotating_platform":
        return _render_rotating_platform(spec, title)
    if kind == "circular_motion":
        return _render_circular_motion(spec, title)
    if kind == "linear_motion":
        return _render_linear_motion(spec, title)
    if kind == "accelerated_motion":
        return _render_accelerated_motion(spec, title)
    if kind == "free_fall":
        return _render_free_fall(spec, title)
    if kind == "projectile_motion":
        return _render_projectile_motion(spec, title)
    if kind == "forces":
        return _render_forces(spec, title)
    if kind == "inclined_plane":
        return _render_inclined_plane(spec, title)
    if kind == "energy_conversion":
        return _render_energy_conversion(spec, title)
    if kind == "momentum_collision":
        return _render_momentum_collision(spec, title)
    if kind == "pressure_buoyancy":
        return _render_pressure_buoyancy(spec, title)
    if kind == "fluid_pressure":
        return _render_fluid_pressure(spec, title)
    if kind == "phase_change":
        return _render_phase_change(spec, title)
    if kind == "gas_process":
        return _render_gas_process(spec, title)
    if kind == "spring":
        return _render_spring(spec, title)
    if kind == "oscillation":
        return _render_oscillation(spec, title)
    if kind == "wave":
        return _render_wave(spec, title)
    if kind == "ray_optics":
        return _render_ray_optics(spec, title)
    if kind == "lens":
        return _render_lens(spec, title)
    if kind == "mirror":
        return _render_mirror(spec, title)
    if kind == "electric_circuit":
        return _render_electric_circuit(spec, title)
    if kind == "electric_field":
        return _render_electric_field(spec, title)
    if kind == "magnetic_field":
        return _render_magnetic_field(spec, title)
    if kind == "electromagnetic_induction":
        return _render_induction(spec, title)
    if kind == "lever":
        return _render_lever(spec, title)
    if kind == "pulley":
        return _render_pulley(spec, title)
    if kind == "measurement":
        return _render_measurement(spec, title)

    parts = _base(title)
    axes = spec.get("axes") or {}
    if axes.get("show"):
        origin = axes.get("origin") or [15, 15]
        if not isinstance(origin, (list, tuple)):
            origin = [15, 15]
        origin_x = origin[0] if len(origin) > 0 else 15
        origin_y = origin[1] if len(origin) > 1 else 15
        ox, oy = _xy(origin_x, origin_y)
        x_len = _num(axes.get("x_length"), 72, 10, 90)
        y_len = _num(axes.get("y_length"), 65, 10, 90)
        x2, _ = _xy(min(100, _num(origin_x, 15, 0, 100) + x_len), origin_y)
        _, y2 = _xy(origin_x, min(100, _num(origin_y, 15, 0, 100) + y_len))
        parts += [
            f'<line x1="{ox:.1f}" y1="{oy:.1f}" x2="{x2:.1f}" y2="{oy:.1f}" stroke="#5b6f89" stroke-width="2.3" marker-end="url(#axisArrow)"/>',
            f'<line x1="{ox:.1f}" y1="{oy:.1f}" x2="{ox:.1f}" y2="{y2:.1f}" stroke="#5b6f89" stroke-width="2.3" marker-end="url(#axisArrow)"/>',
            _svg_text(x2-8, oy+30, axes.get("x_label") or "x", size=23),
            _svg_text(ox+20, y2+10, axes.get("y_label") or "y", size=23),
            _svg_text(ox-25, oy+28, "O", size=20),
        ]

    trajectory = spec.get("trajectory") or []
    d = _path(trajectory)
    if d:
        parts.append(f'<path d="{d}" fill="none" stroke="#1769ff" stroke-width="4" stroke-linecap="round"/>')
        for p in trajectory:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                px, py = _xy(p[0], p[1])
            elif isinstance(p, dict):
                px, py = _xy(p.get("x"), p.get("y"))
            else:
                continue
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4.5" fill="#1769ff"/>')

    for obj in spec.get("objects") or []:
        if not isinstance(obj, dict):
            continue
        typ = str(obj.get("type") or "text").lower()
        x, y = _xy(obj.get("x", 50), obj.get("y", 50))
        label = str(obj.get("label") or "")
        if typ in {"block", "box"}:
            w = _num(obj.get("w"), 16, 4, 60) / 100 * (WIDTH - 2 * MARGIN_X)
            h = _num(obj.get("h"), 11, 4, 45) / 100 * (HEIGHT - 2 * MARGIN_Y)
            fill = "#eef5ff" if typ == "box" else "#dfeaff"
            parts.append(f'<rect x="{x-w/2:.1f}" y="{y-h/2:.1f}" width="{w:.1f}" height="{h:.1f}" rx="14" fill="{fill}" stroke="#1769ff" stroke-width="3"/>')
            parts.append(_svg_text(x, y, label, size=24))
        elif typ == "circle":
            r = _num(obj.get("r"), 3, 1, 15) / 100 * (WIDTH - 2 * MARGIN_X)
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="#1769ff" stroke="#0c4ea8" stroke-width="2"/>')
            if label:
                parts.append(_svg_text(x+14, y-14, label, size=23, anchor="start"))
        elif typ == "ground":
            _, gy = _xy(0, obj.get("y", 20))
            parts.append(f'<line x1="{MARGIN_X}" y1="{gy:.1f}" x2="{WIDTH-MARGIN_X}" y2="{gy:.1f}" stroke="#334e68" stroke-width="4"/>')
        elif typ == "line":
            x2, y2 = _xy(obj.get("x2", obj.get("x", 50)), obj.get("y2", obj.get("y", 50)))
            parts.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#334e68" stroke-width="3"/>')
        elif typ == "text" and label:
            parts.append(_svg_text(x, y, label, size=25))

    for point in spec.get("points") or []:
        if not isinstance(point, dict):
            continue
        x, y = _xy(point.get("x", 50), point.get("y", 50))
        r = _num(point.get("radius"), 1.0, 0.5, 5.0) * 4.5
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="#071c36"/>')
        if point.get("label"):
            parts.append(_svg_text(x+13, y-13, point.get("label"), size=23, anchor="start"))

    for vec in spec.get("vectors") or []:
        if not isinstance(vec, dict):
            continue
        sx, sy = _xy(vec.get("x", 50), vec.get("y", 50))
        ex, ey = _xy(_num(vec.get("x"), 50, 0, 100) + _num(vec.get("dx"), 12, -80, 80), _num(vec.get("y"), 50, 0, 100) + _num(vec.get("dy"), 0, -80, 80))
        parts.append(f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#123b6d" stroke-width="4" marker-end="url(#arrow)"/>')
        if vec.get("label"):
            tx, ty = (sx + ex) / 2 + 12, (sy + ey) / 2 - 12
            parts.append(_svg_text(tx, ty, vec.get("label"), size=25, anchor="start", italic=True))

    return _finish(parts, str(spec.get("caption") or ""))
