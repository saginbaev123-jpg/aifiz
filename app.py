from __future__ import annotations

import math
import base64
import binascii
import json
import os
import random
import re
import time
from html import escape, unescape
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ModuleNotFoundError:
    px = None
    PLOTLY_AVAILABLE = False
import streamlit as st
import streamlit.components.v1 as components

from adaptive.engine import AdaptiveEngine
from adaptive.learning_path import build_learning_path
from adaptive.spaced_repetition import due_topics, next_state, quality_from_result
from ai.error_analyzer import analyze_error
from ai.assessment import numeric_answer_matches
from ai.openai_client import AIClient
from ai.question_generator import clean_descriptors, generate_assignment_tasks, generate_descriptors, generate_diagnostic, generate_pisa, generate_task
from ai.tutor import tutor_reply
from config import ALLOW_USER_API_KEY, APP_MODE, APP_NAME, CLASS_LETTERS, DEFAULT_MODEL, GENERATED_DIR, UPLOAD_DIR, SUPPORTED_GRADES
from core.content import pisa_bank, question_bank, topics_for_grade
from core.database import Database
from core.online_test_choices import online_test_choices
from rag.document_loader import chunk_text, extract_text
from rag.retrieval import format_context, retrieve
from reports.pdf_report import build_student_pdf
from reports.student_report import build_student_docx
from reports.learning_evidence import paired_diagnostics
from reports.online_test_feedback import elapsed_label, focus_recommendations, question_feedback
from teacher_tools import build_docx_bytes, build_pptx_bytes, infer_artifact_kind
from ai_core import AICore
from ai_core.config import CONFIG as AI_CONFIG
from ai_core.files import save_upload
from ai_core.physics_diagrams import render_physics_diagram_svg
from ai_core.visual_engine import infer_diagram_type, validate_diagram_spec

APP_BUILD = "8.3.0"
st.set_page_config(page_title=APP_NAME, page_icon="⚛️", layout="wide")

CUSTOM_CSS = """
<style>
:root {--navy:#071c36;--navy-2:#0b2e59;--blue:#1769ff;--cyan:#20c7e8;--ink:#10213d;--muted:#70809c;--line:#dfe8f4;--surface:#fff;}
html,body,.stApp,[data-testid="stSidebar"],.stApp p,.stApp h1,.stApp h2,.stApp h3,.stApp label,.stApp button,.stApp input,.stApp textarea,.stApp table,.stApp [data-testid="stMetric"]{font-family:"Times New Roman",Times,serif!important;color:var(--ink)}
/* Font inheritance leaves icon fonts and KaTeX's own fonts intact. */
input,textarea,button{font-family:inherit}
[data-testid="stChatMessage"] h1{font-size:1.4rem!important}
[data-testid="stChatMessage"] h2{font-size:1.25rem!important}
[data-testid="stChatMessage"] h3{font-size:1.1rem!important}
[data-testid="stChatMessageContent"]{min-width:0;overflow-wrap:anywhere}
.katex-display{overflow-x:auto;max-width:100%}
.physics-diagram-wrap{background:#fff;border:1px solid var(--line);border-radius:16px;padding:.55rem;margin:.45rem 0 1rem;overflow:hidden}.physics-diagram-wrap svg{display:block;width:100%;height:auto;max-height:620px}
/* Local vector fallback: no remote Material font required. */
[data-testid="stIconMaterial"]{font-size:0!important;display:inline-block;width:20px;height:20px;background:currentColor;mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='m6 9 6 6 6-6' fill='none' stroke='black' stroke-width='2'/%3E%3C/svg%3E") center/contain no-repeat}
[data-testid="stFileUploader"] [data-testid="stIconMaterial"]{display:none}
.material-symbols-rounded,.material-symbols-outlined,.material-icons,[data-testid="stIconMaterial"],[data-testid="stIconMaterial"] *{font-family:"Material Symbols Rounded","Material Symbols Outlined","Material Icons"!important;font-weight:normal!important;font-style:normal!important;letter-spacing:normal!important;text-transform:none!important;white-space:nowrap!important;word-wrap:normal!important;direction:ltr!important;font-feature-settings:"liga"!important;-webkit-font-feature-settings:"liga"!important;-webkit-font-smoothing:antialiased!important}
.stApp{background:linear-gradient(145deg,#f8fbff 0%,#f2f7fd 55%,#f8fbff 100%)}
.block-container{padding-top:1.35rem;padding-bottom:3rem;max-width:1500px}
header[data-testid="stHeader"]{background:transparent} footer{visibility:hidden}
[data-testid="stSidebar"]{background:linear-gradient(180deg,var(--navy) 0%,#082849 62%,#06182d 100%);border-right:0}
[data-testid="stSidebar"] *{color:#eaf4ff}[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p{color:#b9cde4}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:.58rem .72rem;border-radius:12px;margin:.18rem 0;transition:.18s ease}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:rgba(255,255,255,.09)}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:linear-gradient(135deg,#1e75ff,#1456cf);box-shadow:0 10px 24px rgba(0,74,190,.30)}
[data-testid="stSidebar"] hr{border-color:rgba(255,255,255,.13)}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:18px;padding:17px 18px;box-shadow:0 8px 25px rgba(23,69,126,.07)}
[data-testid="stMetricLabel"]{color:var(--muted);font-weight:700}[data-testid="stMetricValue"]{color:var(--ink);font-weight:800}
div.stButton>button,div.stDownloadButton>button{border-radius:11px;font-weight:750;min-height:2.8rem;border:1px solid #cddced}
div.stButton>button[kind="primary"]{background:linear-gradient(135deg,#1d73ff,#1457db);border:0;color:#fff;box-shadow:0 8px 22px rgba(23,105,255,.22)}
[data-testid="stForm"]{background:#fff;border:1px solid var(--line);border-radius:18px;padding:1.15rem;box-shadow:0 8px 28px rgba(23,69,126,.06)}
[data-baseweb="input"]>div,[data-baseweb="textarea"]>div,[data-baseweb="select"]>div{border-radius:11px!important;border-color:#d5e1ef!important;background:#fff!important}
[data-baseweb="select"] span,[data-baseweb="menu"] span,[data-baseweb="input"] input,[data-baseweb="textarea"] textarea,[data-testid="stSidebar"] span{font-family:"Times New Roman",Times,serif!important}
[data-baseweb="tab-list"]{gap:.35rem;background:#eaf1fa;border-radius:12px;padding:.3rem}[data-baseweb="tab"]{border-radius:9px;padding:.6rem 1.1rem}[data-baseweb="tab"][aria-selected="true"]{background:#fff;box-shadow:0 4px 14px rgba(27,72,128,.10)}
.brand-wrap{padding:.55rem .15rem 1.25rem}.brand-row{display:flex;align-items:center;gap:.72rem}.brand-atom{width:42px;height:42px;display:grid;place-items:center;border-radius:13px;background:linear-gradient(135deg,#1d73ff,#21d4ee);font-size:24px;box-shadow:0 8px 24px rgba(29,115,255,.30)}
.brand-name{font-size:1.1rem;font-weight:850;letter-spacing:.2px;color:#fff}.brand-tag{font-size:.78rem;color:#c6dbed;margin-top:.15rem}
.profile-chip{display:flex;gap:.7rem;align-items:center;margin:.4rem 0 1rem;padding:.8rem;border:1px solid rgba(255,255,255,.12);border-radius:14px;background:rgba(255,255,255,.06)}.profile-avatar{width:38px;height:38px;border-radius:50%;display:grid;place-items:center;background:#dceaff;color:#1457db;font-weight:850}.profile-name{font-weight:750;color:#fff}.profile-role{font-size:.75rem;color:#aac1dc}
.page-hero{position:relative;overflow:hidden;border-radius:20px;padding:1.4rem 1.55rem;margin:.1rem 0 1.15rem;background:linear-gradient(115deg,#071f3c 0%,#0d4180 63%,#1472ca 100%);color:#fff;box-shadow:0 14px 34px rgba(7,45,92,.16)}.page-hero:after{content:"⚛";position:absolute;right:2rem;top:-1.4rem;font-size:8rem;color:rgba(78,218,246,.15);transform:rotate(-12deg)}.page-kicker{font-size:.76rem;font-weight:800;letter-spacing:.13em;text-transform:uppercase;color:#67ddf4;margin-bottom:.35rem}.page-title{font-size:clamp(1.65rem,2.5vw,2.45rem);line-height:1.08;font-weight:850;margin:0 0 .45rem;color:#fff}.page-subtitle{font-size:.98rem;color:#c8dbef;max-width:760px;line-height:1.55}
.welcome{background:linear-gradient(118deg,#fff 0%,#f5faff 70%,#eaf7ff 100%);border:1px solid var(--line);border-radius:20px;padding:1.3rem 1.5rem;margin-bottom:1rem;box-shadow:0 9px 28px rgba(23,69,126,.07);position:relative;overflow:hidden}.welcome:after{content:"F = ma";position:absolute;right:2rem;top:1rem;font-family:"Times New Roman",Times,serif;font-style:italic;font-size:2rem;color:#1a70e5;opacity:.10}.welcome h1{margin:0;color:var(--ink);font-size:2rem;font-weight:850}.welcome p{margin:.35rem 0 0;color:var(--muted)}
.ai-card{background:#fff;border:1px solid var(--line);padding:18px;border-radius:17px;margin:8px 0 14px;box-shadow:0 7px 24px rgba(23,69,126,.065)}.feature-card{background:#fff;border:1px solid var(--line);padding:1rem;border-radius:16px;min-height:114px;box-shadow:0 7px 22px rgba(23,69,126,.055)}.feature-icon{width:40px;height:40px;border-radius:12px;display:grid;place-items:center;background:#eaf3ff;font-size:21px;margin-bottom:.6rem}.feature-title{font-weight:800;color:var(--ink)}.feature-copy{font-size:.84rem;color:var(--muted);margin-top:.2rem}
.small-muted{opacity:.72;font-size:.92rem}.good{padding:10px 12px;border-radius:10px;background:#eaf9f1}.bad{padding:10px 12px;border-radius:10px;background:#fff0f1}
.auth-hero{min-height:610px;border-radius:24px;padding:3rem 2.7rem;background:radial-gradient(circle at 65% 45%,rgba(32,199,232,.32),transparent 24%),linear-gradient(145deg,#06182f,#0a3970 65%,#1168aa);color:#fff;position:relative;overflow:hidden;box-shadow:0 20px 50px rgba(5,36,74,.22)}.auth-hero:before{content:"⚛";position:absolute;right:2.5rem;top:8.5rem;font-size:13rem;color:rgba(68,222,247,.25);filter:drop-shadow(0 0 25px rgba(40,195,255,.35))}.auth-hero h1{font-size:2.65rem;line-height:1.05;margin:.8rem 0;color:#fff}.auth-hero p{max-width:460px;color:#c6dcef;font-size:1.05rem;line-height:1.65}.auth-badge{display:inline-flex;gap:.45rem;align-items:center;padding:.4rem .75rem;border:1px solid rgba(255,255,255,.18);border-radius:999px;background:rgba(255,255,255,.08);font-size:.78rem;color:#ccecff}.auth-points{position:absolute;left:2.7rem;right:2.7rem;bottom:2.5rem;display:grid;grid-template-columns:repeat(3,1fr);gap:.7rem}.auth-point{padding:.7rem;border-top:1px solid rgba(255,255,255,.16);font-size:.78rem;color:#c9dcec}.auth-panel-title{font-size:1.9rem;font-weight:850;color:var(--ink);margin:.3rem 0}.auth-panel-sub{color:var(--muted);margin-bottom:1rem}.section-label{font-size:1.15rem;font-weight:850;color:var(--ink);margin:.55rem 0 .65rem}.status-pill{display:inline-flex;align-items:center;gap:.35rem;padding:.28rem .65rem;border-radius:999px;background:#e9f8ef;color:#12814c;font-size:.78rem;font-weight:750}
@media(max-width:900px){.auth-hero{min-height:360px;padding:2rem}.auth-points{position:relative;left:auto;right:auto;bottom:auto;margin-top:7rem}.page-hero:after,.welcome:after{display:none}.block-container{padding-left:1rem;padding-right:1rem}.welcome h1{font-size:1.55rem}}

/* Streamlit ішкі иконкалары мен жасырын input-нұсқауларын мәтінге айналдырмау */
[data-testid="InputInstructions"]{display:none!important}
[data-testid="stChatMessage"]{overflow:visible!important}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"],
.ai-card,.feature-card,.page-subtitle,.pisa-meta-value{overflow-wrap:anywhere!important;word-break:normal!important;white-space:normal!important}
[data-testid="stMarkdownContainer"] p,[data-testid="stMarkdownContainer"] li{line-height:1.55!important}
[data-testid="stMetricValue"],[data-testid="stMetricLabel"]{white-space:normal!important;overflow:visible!important;text-overflow:clip!important}
.pisa-meta-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem;margin:.45rem 0 1.15rem}
.pisa-meta-card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:1rem 1.1rem;box-shadow:0 7px 22px rgba(23,69,126,.055);min-width:0}
.pisa-meta-label{font-size:.82rem;color:var(--muted);font-weight:700;margin-bottom:.35rem}
.pisa-meta-value{font-size:1.25rem;color:var(--ink);font-weight:800;line-height:1.2}
@media(max-width:760px){.pisa-meta-grid{grid-template-columns:1fr}}
[data-testid="stSidebar"]{min-width:255px!important;max-width:285px!important}
[data-testid="stSidebar"] [role="radiogroup"] label{align-items:flex-start;line-height:1.3;overflow-wrap:anywhere}
[data-testid="stSidebar"] [role="radiogroup"] label p{font-size:.94rem!important;color:#eaf4ff!important}
[data-testid="stSidebar"] .stCaption p{color:#c6dbed!important}
[data-testid="stSlider"] [data-testid="stTickBar"]{font-size:.8rem}
button:focus-visible,[role="radio"]:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid #49b9ee!important;outline-offset:2px!important}
.empty-card{padding:1.5rem;border:1px solid var(--line);background:#fff;border-radius:18px;box-shadow:0 8px 25px rgba(23,69,126,.06)}
.page-hero{padding:1.05rem 1.4rem;margin-bottom:.9rem}.page-hero:after{font-size:6rem;top:-.8rem}.page-title{font-size:clamp(1.6rem,2.2vw,2.15rem)}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

DB = Database()
TASKS = question_bank()
camera_recorder = components.declare_component("question_camera_recorder", path=str(Path(__file__).resolve().parent / "camera_component"))
PISA_TASKS = pisa_bank()


ERROR_LABELS = {
    "FORMULA_ERROR": "Формуланы қолдану қатесі",
    "SI_ERROR": "SI жүйесіне түрлендіру қатесі",
    "CALCULATION_ERROR": "Есептеу қатесі",
    "CONCEPT_ERROR": "Физикалық ұғым қатесі",
    "VECTOR_ERROR": "Векторлық шама қатесі",
    "GRAPH_ERROR": "Графикті талдау қатесі",
    "UNIT_ERROR": "Өлшем бірлік қатесі",
    "READING_ERROR": "Шартты түсіну қатесі",
}

def error_label(code: str | None) -> str:
    return ERROR_LABELS.get(str(code or ""), str(code or "Белгісіз қате"))

def plotly_tnr(fig):
    if fig is None:
        return None
    fig.update_layout(font=dict(family="Times New Roman"))
    return fig


def safe_bar_chart(df: pd.DataFrame, *, x: str, y: str, orientation: str = "v", title: str | None = None, range_max: float | None = None) -> None:
    """Render with Plotly when available, otherwise use Streamlit's built-in chart."""
    if df.empty or x not in df.columns or y not in df.columns:
        return
    if title:
        st.markdown(f"**{escape(title)}**")
    if PLOTLY_AVAILABLE:
        kwargs = {"x": x, "y": y, "orientation": orientation}
        if orientation == "h" and range_max is not None:
            kwargs["range_x"] = [0, range_max]
        elif orientation != "h" and range_max is not None:
            kwargs["range_y"] = [0, range_max]
        fig = px.bar(df, **kwargs)
        st.plotly_chart(plotly_tnr(fig), use_container_width=True)
        return
    try:
        if orientation == "h":
            st.bar_chart(df.set_index(y)[x])
        else:
            st.bar_chart(df.set_index(x)[y])
    except Exception:
        st.dataframe(df[[x, y]], hide_index=True, use_container_width=True)


def safe_line_chart(df: pd.DataFrame, *, x: str, y: str, title: str | None = None, range_max: float | None = None) -> None:
    if df.empty or x not in df.columns or y not in df.columns:
        return
    if title:
        st.markdown(f"**{escape(title)}**")
    if PLOTLY_AVAILABLE:
        kwargs = {"x": x, "y": y, "markers": True}
        if range_max is not None:
            kwargs["range_y"] = [0, range_max]
        fig = px.line(df, **kwargs)
        st.plotly_chart(plotly_tnr(fig), use_container_width=True)
        return
    try:
        st.line_chart(df.set_index(x)[y])
    except Exception:
        st.dataframe(df[[x, y]], hide_index=True, use_container_width=True)


def page_header(title: str, subtitle: str, kicker: str = "AI PHYSICS KZ") -> None:
    st.markdown(
        f"""<section class="page-hero"><div class="page-kicker">{escape(kicker)}</div>
        <div class="page-title">{escape(title)}</div><div class="page-subtitle">{escape(subtitle)}</div></section>""",
        unsafe_allow_html=True,
    )


def feature_card(icon: str, title: str, copy: str) -> None:
    st.markdown(
        f"<div class='feature-card'><div class='feature-icon'>{icon}</div><div class='feature-title'>{escape(title)}</div><div class='feature-copy'>{escape(copy)}</div></div>",
        unsafe_allow_html=True,
    )


def go_to(page: str) -> None:
    st.session_state["nav_page"] = page


def init_state() -> None:
    defaults = {
        "user": None,
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "model": os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        "current_task": None,
        "adaptive_feedback": None,
        "diagnostic_seed": None,
        "pisa_current": None,
        "diagnostic_pool": None,
        "diagnostic_grade": None,
        "teacher_assignment_draft": None,
        "teacher_pisa_draft": None,
        "teacher_assistant_artifact": None,
        "teacher_assistant_retry_prompt": None,
        "teacher_assistant_pending_prompt": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def ai_client() -> AIClient:
    return AIClient(st.session_state.get("api_key"), st.session_state.get("model"))


def numeric_value(text: str) -> float | None:
    if text is None:
        return None
    s = str(text).strip().replace(",", ".")
    match = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", s)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def evaluate_task(task: dict[str, Any], answer: str) -> bool:
    if task.get("type") == "numeric":
        return numeric_answer_matches(str(task.get("answer", "")), answer, task.get("tolerance"))
    return str(answer).strip().lower() == str(task.get("answer", "")).strip().lower()


def normalize_math(text: str) -> str:
    """ЖИ мәтінін техникалық қалдықсыз Streamlit/KaTeX форматына келтіреді."""
    from ai_core.math_text import prepare_math
    return prepare_math(text)


_SVG_BLOCK_RE = re.compile(r"(?is)(?:```(?:svg|xml|html)?\s*)?(<svg\b.*?</svg>)(?:\s*```)?")
_SVG_UNSAFE_RE = re.compile(r"(?is)<\s*(?:script|foreignObject|iframe|object|embed|image|a|style)\b|\son[a-z]+\s*=|javascript\s*:")


def _decode_markup_text(value: str) -> str:
    """Decode model/database escaped SVG before detection.

    Old chat rows can contain &lt;svg&gt; or literal \u003csvg forms.  Keeping
    this in the renderer makes already-saved answers repair themselves without
    deleting the conversation database.
    """
    text = str(value or "")
    text = text.replace("\\u003c", "<").replace("\\u003e", ">").replace("\\u0026", "&")
    text = text.replace("\\n", "\n") if "<svg" in text or "&lt;svg" in text else text
    for _ in range(2):
        decoded = unescape(text)
        if decoded == text:
            break
        text = decoded
    return text


def _safe_svg_markup(svg: str) -> str | None:
    """Accept only small, self-contained SVG markup suitable for inline display."""
    value = _decode_markup_text(svg).strip()
    if not value.lower().startswith("<svg") or "</svg>" not in value.lower():
        return None
    if _SVG_UNSAFE_RE.search(value):
        return None
    # External resources are not needed for physics diagrams and are blocked.
    if re.search(r"(?is)\b(?:href|xlink:href)\s*=", value):
        return None
    return value


def render_svg(svg: str, *, height: int = 390) -> bool:
    """Render SVG as an actual responsive diagram instead of exposing its source code."""
    safe = _safe_svg_markup(svg)
    if not safe:
        return False
    html = f"""
    <html><head><meta charset="utf-8"><style>
    html,body{{margin:0;padding:0;background:transparent;overflow:hidden}}
    .wrap{{box-sizing:border-box;width:100%;background:#fff;border:1px solid #dfe8f4;border-radius:16px;padding:8px;overflow:hidden}}
    .wrap svg{{display:block;width:100%!important;height:auto!important;max-height:{max(220, int(height)-18)}px}}
    text{{font-family:'Times New Roman',Times,serif}}
    </style></head><body><div class="wrap">{safe}</div></body></html>
    """
    components.html(html, height=max(240, int(height)), scrolling=False)
    return True


def render_rich_text(text: str) -> None:
    """Render Markdown/LaTeX and repair leaked/escaped inline SVG from old or new answers."""
    raw = _decode_markup_text(str(text or ""))
    if not raw.strip():
        return
    cursor = 0
    matched = False
    for match in _SVG_BLOCK_RE.finditer(raw):
        matched = True
        before = raw[cursor:match.start()]
        # Remove an orphan opening code fence that preceded the SVG.
        before = re.sub(r"(?is)```(?:svg|xml|html)?\s*$", "", before)
        before = normalize_math(before)
        if before.strip():
            st.markdown(before)
        svg = match.group(1)
        if not render_svg(svg):
            st.caption("Сызбаны қауіпсіз түрде көрсету мүмкін болмады.")
        cursor = match.end()
    tail = raw[cursor:] if matched else raw
    tail = re.sub(r"(?is)^\s*```\s*", "", tail) if matched else tail
    tail = normalize_math(tail)
    if tail.strip():
        st.markdown(tail)


def _repair_pisa_diagram_spec(task: dict[str, Any], visual: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Repair old and new PISA diagram payloads through the universal validator."""
    semantic = " ".join([
        str(task.get("topic") or ""),
        str(task.get("title") or ""),
        str(task.get("scenario") or ""),
        str(visual.get("title") or ""),
        str((spec or {}).get("caption") or ""),
    ])
    return validate_diagram_spec(spec or {}, context=semantic, title=str(task.get("title") or task.get("topic") or "Физикалық сызба")).spec

def analyze_notebook_submission(ai: AIClient, assignment: dict[str, Any], items: list[dict[str, Any]], image_bytes: bytes, mime: str) -> dict[str, Any]:
    scored_items = [(i, clean_descriptors(x["task"].get("descriptors"))) for i, x in enumerate(items, 1)]
    if scored_items and all(descriptors for _, descriptors in scored_items):
        if not ai.available:
            return {"score": 0.0, "feedback": "Жұмыс сақталды. ЖИ бағалауы қолжетімсіз, мұғалім тексереді.", "answers": [], "graded": False}
        rubric = [{"question_index": i, "question": items[i-1]["task"].get("question", ""),
                   "answer": items[i-1]["task"].get("answer", ""),
                   "solution": items[i-1]["task"].get("solution", ""), "descriptors": descriptors}
                  for i, descriptors in scored_items]
        try:
            data = ai.vision_json(
                "Сен физика мұғалімісің. Суретте шынымен көрінген жазбаны ғана бағала. "
                "Әр сұрақтың әр дескрипторы бойынша дәлелді көрсетіп, 0-ден берілген баллға дейін бүтін балл бер. "
                "Көрінбейтін жауапқа немесе өлшем бірлігі жоқ жазбаға балл ойдан қоспа. Тек JSON объект бер.",
                f"Дәптерді бекітілген дескрипторлар бойынша тексер:\n{json.dumps(rubric, ensure_ascii=False)}\n"
                'JSON: {"answers":[{"question_index":1,"student_answer":"суреттегі жазылған жауап",'
                '"feedback":"қысқа түсіндірме","descriptors":[{"index":1,"awarded_points":0,"evidence":"суретте бар нақты жазба не жоқ"}]}]}. '
                "question_index және index 1-ден басталады. Барлық сұрақ пен барлық дескрипторды келтір, орындалмағанына 0 бер.",
                image_bytes, mime,
            )
            rows = data.get("answers") if isinstance(data, dict) else None
            if not isinstance(rows, list):
                raise ValueError("No descriptor assessment")
            by_index = {}
            for row in rows:
                if isinstance(row, dict):
                    try:
                        index = int(row.get("question_index"))
                    except (ValueError, TypeError):
                        continue
                    if index not in by_index:
                        by_index[index] = row
            if set(by_index) != set(range(1, len(items)+1)):
                raise ValueError("Incomplete question assessment")
            answers = []
            total_awarded = total_possible = 0
            for index, descriptors in scored_items:
                row = by_index[index]
                checks = row.get("descriptors")
                if not isinstance(checks, list):
                    raise ValueError("Missing descriptor assessment")
                by_desc = {}
                for check in checks:
                    if isinstance(check, dict):
                        try:
                            desc_index = int(check.get("index"))
                        except (ValueError, TypeError):
                            continue
                        if desc_index not in by_desc:
                            by_desc[desc_index] = check
                if set(by_desc) != set(range(1, len(descriptors)+1)):
                    raise ValueError("Incomplete descriptor assessment")
                awarded = 0
                details = []
                for desc_index, desc in enumerate(descriptors, 1):
                    check = by_desc[desc_index]
                    raw_points = float(check.get("awarded_points"))
                    if not raw_points.is_integer():
                        raise ValueError("Non-integer descriptor points")
                    points = max(0, min(desc["points"], int(raw_points)))
                    awarded += points
                    details.append(f"{desc['description']}: {points}/{desc['points']} балл. {str(check.get('evidence') or '').strip()}")
                possible = sum(desc["points"] for desc in descriptors)
                total_awarded += awarded
                total_possible += possible
                answers.append({"question_index": index, "student_answer": str(row.get("student_answer") or "").strip(),
                                "correct": awarded == possible, "score": 100 * awarded / possible,
                                "feedback": f"{awarded}/{possible} балл. " + " ".join(details) + " " + str(row.get("feedback") or "")})
            return {"score": 100 * total_awarded / total_possible, "feedback":
                    f"Дескрипторлар бойынша {total_awarded}/{total_possible} балл. " +
                    " ".join(f"{a['question_index']}-тапсырма: {a['feedback']}" for a in answers),
                    "answers": answers, "graded": True}
        except Exception:
            return {"score": 0.0, "feedback": "Жұмыс сақталды. Дескрипторлар бойынша бағалау аяқталмады, мұғалім тексереді.", "answers": [], "graded": False}
    questions = "\n".join(
        f"{i+1}. {x['task'].get('question','')}\nКүтілетін жауап: {x['task'].get('answer','')}\nШешім үлгісі: {x['task'].get('solution','')}"
        for i, x in enumerate(items)
    )
    if not ai.available:
        return {"score": 0.0, "feedback": "Жұмыс сақталды және мұғалімге жіберілді. Автоматты тексеру уақытша қолжетімсіз; мұғалім жұмысты өзі тексереді.", "answers": []}
    try:
        data = ai.vision_json(
            "Сен физика мұғалімісің. Оқушының дәптердегі қолжазба жұмысын суреттен оқы. Әр есеп бойынша оқушының нақты жазған соңғы жауабын, негізгі шығару жолын, формулаларын және өлшем бірліктерін тексер. Берілмеген жауапты ойдан шығарма. Қазақ тілінде қысқа және нақты бағала.",
            f"Тақырып: {assignment['topic']}\nДеңгей: {assignment['difficulty']}\nТапсырмалар мен мұғалімдегі тексеру деректері:\n{questions}\n\nJSON объект бер: score (0-100), feedback және answers массиві. answers ішіндегі әр объект: question_index (1-ден басталады), student_answer (суреттен оқылған жауап), correct (true/false), score (0-100), feedback (қысқа түсіндірме).",
            image_bytes, mime
        )
        score = max(0.0, min(100.0, float(data.get("score", 0))))
        feedback = str(data.get("feedback") or "Жұмыс тексерілді.")
        raw_answers = data.get("answers") if isinstance(data.get("answers"), list) else []
        answers = []
        for row in raw_answers:
            if not isinstance(row, dict):
                continue
            try:
                qidx = int(row.get("question_index", 0))
            except Exception:
                continue
            if not (1 <= qidx <= len(items)):
                continue
            answers.append({
                "question_index": qidx,
                "student_answer": str(row.get("student_answer") or "").strip(),
                "correct": bool(row.get("correct")),
                "score": max(0.0, min(100.0, float(row.get("score", 100 if row.get("correct") else 0)))),
                "feedback": str(row.get("feedback") or "").strip(),
            })
        return {"score": score, "feedback": feedback, "answers": answers}
    except Exception:
        return {"score": 0.0, "feedback": "Жұмыс сақталды және мұғалімге жіберілді. Автоматты тексеру уақытша аяқталмады; мұғалім жұмысты өзі тексереді.", "answers": []}


def auth_screen() -> None:
    left, right = st.columns([1.25, .82], gap="large")
    with left:
        st.markdown(
            """<section class="auth-hero"><div class="auth-badge">⚛ ЖАҢА БУЫН БІЛІМ ПЛАТФОРМАСЫ</div>
            <h1>AI PHYSICS<br><span style="color:#41dcf4">KZ</span></h1>
            <p>Диагностика, жеке оқу траекториясы, тапсырмалар және ЖИ мұғалім — барлығы бір қауіпсіз ортада.</p>
            <div class="auth-points"><div class="auth-point">🧠 Жеке диагностика</div><div class="auth-point">🎯 Бейімделген оқу</div><div class="auth-point">📈 Нақты прогресс</div></div></section>""",
            unsafe_allow_html=True,
        )
    with right:
        st.markdown("<div class='auth-panel-title'>Жүйеге кіру</div><div class='auth-panel-sub'>Өз кабинетіңізді ашып, оқуды жалғастырыңыз.</div>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["Кіру", "Тіркелу"])
        with tab1:
            with st.form("login_form"):
                username = st.text_input("Логин", placeholder="Логиніңізді енгізіңіз")
                password = st.text_input("Құпиясөз", type="password", placeholder="••••••••")
                ok = st.form_submit_button("Кіру  →", use_container_width=True, type="primary")
            if ok:
                user = DB.authenticate(username, password)
                if user:
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Логин немесе құпиясөз дұрыс емес.")
        with tab2:
            with st.form("register_form"):
                full_name = st.text_input("Аты-жөні")
                username = st.text_input("Логин", key="reg_user")
                password = st.text_input("Құпиясөз (кемінде 6 таңба)", type="password", key="reg_pass")
                role_label = st.selectbox("Рөл", ["Оқушы", "Мұғалім"])
                if role_label == "Оқушы":
                    c_grade, c_letter = st.columns([2, 1])
                    grade = c_grade.selectbox("Сынып", SUPPORTED_GRADES, index=2)
                    class_letter = c_letter.selectbox("Әріп", CLASS_LETTERS, index=0)
                    join_code = st.text_input("Сынып коды *", placeholder="Мұғалім берген кодты енгізіңіз")
                    st.caption(f"Оқушы профилі: {grade}{class_letter}. Сынып кодынсыз тіркелу мүмкін емес.")
                else:
                    grade, class_letter, join_code = None, None, ""
                create = st.form_submit_button("Аккаунт құру", use_container_width=True, type="primary")
            if create:
                if len(password) < 6 or not username.strip() or not full_name.strip():
                    st.error("Аты-жөні, логин және кемінде 6 таңбалы құпиясөз қажет.")
                elif role_label == "Оқушы" and not join_code.strip():
                    st.error("Сынып кодын енгізу міндетті. Кодсыз оқушы тіркеле алмайды.")
                elif role_label == "Оқушы" and not DB.class_by_code(join_code):
                    st.error("Сынып коды дұрыс емес. Мұғалім берген кодты қайта тексеріңіз.")
                elif role_label == "Оқушы":
                    cls = DB.class_by_code(join_code)
                    match = re.match(r"^\s*(\d{1,2})\s*[- ]?\s*([А-ЯӘҒҚҢӨҰҮҺA-Z])?", str(cls.get("name", "")).upper()) if cls else None
                    code_grade = int(match.group(1)) if match else None
                    code_letter = (match.group(2) or "") if match else ""
                    latin_map = {"A":"А","B":"Б","V":"В","G":"Г","D":"Д","E":"Е","K":"К","M":"М"}
                    code_letter = latin_map.get(code_letter, code_letter)
                    if code_grade != int(grade) or (code_letter and code_letter != str(class_letter).upper()):
                        st.error("Сынып коды таңдалған сыныпқа сәйкес келмейді. Сынып пен әріпті қайта тексеріңіз.")
                    else:
                        try:
                            uid, class_name = DB.register_student_with_class(username, password, full_name, join_code)
                            st.success(f"Тіркелу аяқталды. {class_name} сыныбына қосылдыңыз. Енді жүйеге кіріңіз.")
                        except Exception as e:
                            st.error("Бұл логин бұрын тіркелген." if "UNIQUE" in str(e).upper() else "Тіркелу аяқталмады. Енгізілген деректерді тексеріп, қайта көріңіз.")
                else:
                    try:
                        DB.register_user(username, password, full_name, "teacher", None, None)
                        st.success("Тіркелу аяқталды. Енді жүйеге кіріңіз.")
                    except Exception as e:
                        st.error("Бұл логин бұрын тіркелген." if "UNIQUE" in str(e).upper() else "Тіркелу аяқталмады. Енгізілген деректерді тексеріп, қайта көріңіз.")


def sidebar() -> str:
    user = st.session_state.user
    st.sidebar.markdown("""<div class="brand-wrap"><div class="brand-row"><div class="brand-atom">⚛</div><div><div class="brand-name">AI PHYSICS KZ</div><div class="brand-tag">Білім • Технология • Болашақ</div></div></div></div>""", unsafe_allow_html=True)
    if user["role"] == "student":
        cls_label = f"{int(user.get('grade') or 9)}{user.get('class_letter') or ''}"
        role_text = f"Оқушы • {cls_label} сыныбы"
    else:
        role_text = "Физика пәні мұғалімі"
    initials = "".join(x[:1] for x in user["full_name"].split()[:2]).upper() or "AI"
    st.sidebar.markdown(f"<div class='profile-chip'><div class='profile-avatar'>{escape(initials)}</div><div><div class='profile-name'>{escape(user['full_name'])}</div><div class='profile-role'>{escape(role_text)}</div></div></div>", unsafe_allow_html=True)
    if user["role"] == "student":
        pages = ["Басты бет", "Диагностика", "Адаптивті оқу", "Тапсырмалар", "Функционалдық сауаттылық және PISA", "Қатемен жұмыс", "ЖИ мұғалім", "Прогресс", "Профиль", "Баптаулар"]
    else:
        pages = ["Мұғалім панелі", "Сыныптар", "Оқушылар", "Сынып тапсырмалары", "Функционалдық сауаттылық және PISA", "Мұғалім ЖИ ассистенті", "Материалдар", "Тапсырма генераторы", "Баптаулар"]
    page = st.sidebar.radio("Навигация", pages, label_visibility="collapsed", key="nav_page")
    st.sidebar.divider()
    st.sidebar.caption("Физика — әлемді түсінудің кілті")
    st.sidebar.caption(f"Жүйе нұсқасы: {APP_BUILD}")
    if st.sidebar.button("↪  Жүйеден шығу", use_container_width=True):
        st.session_state.user = None
        st.session_state.current_task = None
        st.rerun()
    return page


def refresh_user() -> dict[str, Any]:
    u = DB.get_user(int(st.session_state.user["id"]))
    if u:
        st.session_state.user = u
    return st.session_state.user


def ensure_student_topics(user: dict[str, Any]) -> list[str]:
    grade = int(user.get("grade") or 9)
    topics = topics_for_grade(grade)
    DB.ensure_topics(int(user["id"]), grade, topics)
    return topics


def metric_row(student_id: int, grade: int):
    mastery = DB.get_mastery(student_id, grade)
    diagnostics = DB.diagnostic_history(student_id)
    attempts = DB.attempts(student_id, 500)
    measured = [r for r in mastery if int(r.get("attempts") or 0) > 0]
    avg = sum(float(r["score"]) for r in measured) / len(measured) if measured else None
    latest_diag = diagnostics[0]["percent"] if diagnostics else None
    answered = [a for a in attempts if a.get("is_correct") is not None]
    acc = 100 * sum(int(a["is_correct"]) for a in answered) / len(answered) if answered else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Жалпы прогресс", f"{avg:.0f}%" if avg is not None else "—", "нақты орындалған тапсырмалар")
    c2.metric("Соңғы диагностика", f"{latest_diag:.0f}%" if latest_diag is not None else "—", "білім деңгейі")
    c3.metric("Тапсырма дәлдігі", f"{acc:.0f}%" if answered else "—", "дұрыс жауап")
    c4.metric("Орындалған тапсырма", len(answered), "барлық әрекет")


def page_student_home(user: dict[str, Any]) -> None:
    grade = int(user.get("grade") or 9)
    topics = ensure_student_topics(user)
    mastery = DB.get_mastery(user["id"], grade)
    mistakes = DB.get_mistakes(user["id"])
    states = DB.all_review_states(user["id"])
    due = due_topics(states)
    path = build_learning_path(mastery, mistakes)

    first_name = user["full_name"].split()[0]
    st.markdown(f"<section class='welcome'><span class='status-pill'>● ОҚУ ЖОСПАРЫ БЕЛСЕНДІ</span><h1>Қайырлы күн, {escape(first_name)}!</h1><p>{grade}{escape(user.get('class_letter') or '')} сыныбы • Бүгін де мақсатыңа бір қадам жақында.</p></section>", unsafe_allow_html=True)
    metric_row(user["id"], grade)

    st.markdown("<div class='section-label'>Жылдам бастау</div>", unsafe_allow_html=True)
    q1, q2, q3, q4 = st.columns(4)
    with q1:
        feature_card("🧠", "ЖИ диагностика", "Білім деңгейіңді анықта")
        st.button("Диагностиканы бастау", use_container_width=True, on_click=go_to, args=("Диагностика",))
    with q2:
        feature_card("🎯", "Жеке оқу", "Өзіңе сай тапсырма ал")
        st.button("Оқуды жалғастыру", use_container_width=True, on_click=go_to, args=("Адаптивті оқу",))
    with q3:
        feature_card("⚗", "Тапсырмалар", "Өмірлік есептерді зертте")
        st.button("Тапсырмаларға кіру", use_container_width=True, on_click=go_to, args=("Функционалдық сауаттылық және PISA",))
    with q4:
        feature_card("🤖", "ЖИ мұғалім", "Сұрағыңа түсінікті жауап ал")
        st.button("Сұрақ қою", use_container_width=True, on_click=go_to, args=("ЖИ мұғалім",))

    left, right = st.columns([1.5, 1])
    with left:
        st.markdown("<div class='section-label'>Тақырыптық прогресс</div>", unsafe_allow_html=True)
        measured_mastery = [r for r in mastery if int(r.get("attempts") or 0) > 0]
        if measured_mastery:
            df = pd.DataFrame(measured_mastery)
            if PLOTLY_AVAILABLE:
                fig = px.bar(df, x="score", y="topic", orientation="h", range_x=[0, 100], labels={"score":"Меңгеру, %","topic":"Тақырып"}, color="score", color_continuous_scale=["#dceaff","#1769ff"])
                fig.update_layout(height=max(320, 48 * len(df)), margin=dict(l=10,r=10,t=20,b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", coloraxis_showscale=False)
                st.plotly_chart(plotly_tnr(fig), use_container_width=True)
            else:
                safe_bar_chart(df, x="score", y="topic", orientation="h", range_max=100)
        else:
            st.info("Тақырыптық прогресс тапсырмалар орындалғаннан кейін көрсетіледі.")
    with right:
        st.markdown("<div class='section-label'>Бүгінгі оқу жоспары</div>", unsafe_allow_html=True)
        if path:
            p = path[0]
            st.markdown(f"<div class='ai-card'><span class='status-pill'>ҰСЫНЫЛҒАН</span><h3 style='margin:.7rem 0 .3rem'>{escape(str(p['topic']))}</h3><div class='small-muted'>Меңгеру деңгейі: {escape(str(p['score']))}</div><p>{escape(str(p['action']))}</p></div>", unsafe_allow_html=True)
        if due:
            st.info("Қайталау уақыты келген тақырыптар: " + ", ".join(due[:4]))
        elif states:
            st.success("Жоспарланған шұғыл қайталау жоқ.")
        else:
            st.caption("Тапсырмаларды орындаған сайын қайталау кестесі автоматты құрылады.")

    st.markdown("<div class='section-label'>Жеке оқу траекториясы</div>", unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(path).rename(columns={"topic":"Тақырып","score":"Меңгеру","action":"Ұсынылатын әрекет"}), use_container_width=True, hide_index=True)


def local_diagnostic_questions(grade: int) -> list[dict[str, Any]]:
    pool = [t for t in TASKS if int(t.get("grade", 0)) == grade]
    if not pool:
        return []
    # Prefer balanced topic coverage and no more than 12 questions.
    by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in pool:
        by_topic[t["topic"]].append(t)
    chosen = []
    for topic, arr in by_topic.items():
        arr = sorted(arr, key=lambda x: {"A":0,"B":1,"C":2}.get(x.get("difficulty"), 1))
        chosen.extend(arr[:2])
    if len(chosen) < 12:
        remaining = [t for t in pool if t not in chosen]
        chosen.extend(remaining[:12-len(chosen)])
    return chosen[:12]


def page_diagnostic(user: dict[str, Any]) -> None:
    grade = int(user.get("grade") or 9)
    topics = ensure_student_topics(user)
    page_header("ЖИ диагностика", "Білім деңгейіңді анықта және жеке ұсыныстар ал.", "ЖЕКЕ БАҒАЛАУ")

    history = DB.attempts(user["id"], 120)
    diagnostic_history = DB.diagnostic_history(user["id"])
    chosen_scope = st.selectbox("Бағалау тақырыбы", ["Барлық тақырыптар"] + topics)
    focus_topic = None if chosen_scope == "Барлық тақырыптар" else chosen_scope
    baseline = next((d for d in diagnostic_history if d.get("focus_topic") == focus_topic and d.get("phase") == "baseline"), None) if focus_topic else None
    phase = None
    if focus_topic:
        phase = st.radio("Бағалау кезеңі", ["Бастапқы", "Қорытынды"], horizontal=True)
        if phase == "Қорытынды" and not baseline:
            st.info("Алдымен осы тақырып бойынша бастапқы диагностикадан өтіңіз.")
            return
        if phase == "Қорытынды":
            st.caption(f"Бастапқы нәтиже: {baseline['percent']:.1f}% · {baseline['total']} сұрақ")
    old_questions = [a.get("question_text", "") for a in history if a.get("activity_type") == "diagnostic"]
    c1, c2 = st.columns([2, 1])
    with c1:
        diagnostic_options = [8, 10, 12, 15]
        selected_count = int(baseline["total"]) if phase == "Қорытынды" else 12
        if selected_count not in diagnostic_options:
            diagnostic_options.append(selected_count)
            diagnostic_options.sort()
        count = st.selectbox("Сұрақ саны", diagnostic_options, index=diagnostic_options.index(selected_count), disabled=phase == "Қорытынды")
    with c2:
        if st.button("Жаңа ЖИ диагностикасын құру", use_container_width=True, type="primary"):
            if not ai_client().available:
                st.error("Жүйенің тапсырма құрастыру қызметі уақытша қолжетімсіз.")
            else:
                with st.spinner("ЖИ диагностикалық тапсырмаларды құрастырып жатыр..."):
                    pool = generate_diagnostic(ai_client(), grade, [focus_topic] if focus_topic else topics, count, avoid_questions=old_questions)
                if pool:
                    st.session_state.diagnostic_pool = pool
                    st.session_state.diagnostic_grade = grade
                    st.session_state.diagnostic_scope = (focus_topic, phase)
                    st.success(f"{len(pool)} жаңа диагностикалық сұрақ дайын.")
                    st.rerun()
                else:
                    st.error("Диагностиканы құру сәтсіз аяқталды. Қайта көріңіз.")

    pool = st.session_state.get("diagnostic_pool")
    if st.session_state.get("diagnostic_grade") != grade or st.session_state.get("diagnostic_scope") != (focus_topic, phase):
        pool = None
        st.session_state.diagnostic_pool = None
    if not pool:
        st.info("Диагностиканы бастау үшін «Жаңа ЖИ диагностикасын құру» батырмасын басыңыз.")
        if not ai_client().available and phase != "Қорытынды":
            if st.button("Дайын диагностикалық тапсырмаларды бастау", use_container_width=True):
                local = local_diagnostic_questions(grade)
                st.session_state.diagnostic_pool = [q for q in local if q["topic"] == focus_topic] if focus_topic else local
                st.session_state.diagnostic_grade = grade
                st.session_state.diagnostic_scope = (focus_topic, phase)
                st.rerun()
        elif not ai_client().available and phase == "Қорытынды":
            st.warning("Қорытынды бағалауға бастапқы тест сұрақтарын қайталамайтын жаңа тапсырмалар қажет. ЖИ қызметін қосып, қайта көріңіз.")
        return

    with st.form("diagnostic_form"):
        answers: dict[str, str] = {}
        for i, task in enumerate(pool, 1):
            st.markdown(f"**{i}. [{task['topic']}] • {task.get('difficulty','B')} деңгей**")
            st.write(task["question"])
            if task["type"] == "mcq":
                answers[task["id"]] = st.radio("Жауап", ["— таңдаңыз —"] + task["options"], key=f"diag_{task['id']}", horizontal=True)
            else:
                answers[task["id"]] = st.text_input("Жауап", key=f"diag_{task['id']}")
            st.divider()
        submitted = st.form_submit_button("Диагностиканы аяқтау", use_container_width=True)
    if submitted:
        if not pool:
            st.error("Бұл тақырып бойынша дайын сұрақтар жоқ; ЖИ тапсырмаларын құруды қолданыңыз.")
            return
        if phase == "Қорытынды" and len(pool) != int(baseline["total"]):
            st.error("Әділ салыстыру үшін қорытынды диагностикадағы сұрақ саны бастапқы тестпен бірдей болуы керек.")
            return
        if any(v in {"", "— таңдаңыз —"} for v in answers.values()):
            st.error("Барлық сұраққа жауап беріңіз.")
            return
        topic_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"correct":0,"total":0})
        total_correct = 0
        for task in pool:
            ans = answers[task["id"]]
            ok = evaluate_task(task, ans)
            topic_stats[task["topic"]]["total"] += 1
            topic_stats[task["topic"]]["correct"] += int(ok)
            total_correct += int(ok)
            DB.log_attempt(
                student_id=user["id"], activity_type="diagnostic", topic=task["topic"], difficulty=task["difficulty"],
                question_id=task["id"], question_text=task["question"], student_answer=ans, correct_answer=task["answer"],
                is_correct=int(ok), confidence=3, score=100 if ok else 0, error_type=None if ok else task.get("error_hint"),
                feedback=task["solution"],
            )
            if not ok:
                DB.record_mistake(user["id"], task["topic"], task.get("error_hint","CONCEPT_ERROR"), "Диагностикада анықталған қате")
        for topic, stat in topic_stats.items():
            pct = 100 * stat["correct"] / stat["total"] if stat["total"] else 0
            DB.set_mastery(user["id"], grade, topic, pct, stat["total"], stat["correct"])
        DB.save_diagnostic(user["id"], grade, len(pool), total_correct, dict(topic_stats), focus_topic, {"Бастапқы": "baseline", "Қорытынды": "final"}.get(phase))
        percent = 100 * total_correct / len(pool)
        st.success(f"Диагностика аяқталды: {total_correct}/{len(pool)} — {percent:.1f}%")
        rows = []
        for topic, stat in topic_stats.items():
            rows.append({"Тақырып":topic,"Дұрыс":stat["correct"],"Барлығы":stat["total"],"Нәтиже":f"{100*stat['correct']/stat['total']:.0f}%"})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        weakest = sorted(rows, key=lambda r: float(r["Нәтиже"].replace("%","")))[:3]
        st.info("Жеке оқу бағыты: " + " → ".join(r["Тақырып"] for r in weakest))
        if phase == "Қорытынды" and baseline:
            st.metric("Бастапқы нәтижемен салыстырғандағы өзгеріс", f"{percent:.1f}%", f"{percent - baseline['percent']:+.1f} пайыздық тармақ")
        st.session_state.diagnostic_pool = None


def current_topic_score(user_id: int, grade: int, topic: str) -> float:
    rows = DB.get_mastery(user_id, grade)
    for r in rows:
        if r["topic"] == topic:
            return float(r["score"]) if int(r.get("attempts") or 0) > 0 else 0.0
    return 0.0


def adaptive_new_task(user: dict[str, Any], topic: str, mistake: dict[str, Any] | None = None) -> None:
    grade = int(user.get("grade") or 9)
    attempts = [a for a in DB.attempts(user["id"], 60) if a["topic"] == topic]
    score = current_topic_score(user["id"], grade, topic)
    level = AdaptiveEngine.recommended_level(score, attempts)
    if mistake and level == "C":
        level = "B"
    elif mistake and level == "B":
        level = "A"
    recent_questions = [str(a.get("question_text") or "") for a in attempts[:8]]
    mistake_context = ""
    if mistake:
        mistake_context = f"Қайталанатын қате: {mistake.get('mistake_type')} — {mistake.get('description')}. Осы қатені түзетуге бағытталған тапсырма бер."
    task = generate_task(
        ai_client(), grade, topic, level,
        mastery=score,
        mistake_context=mistake_context,
        avoid_questions=recent_questions,
    )
    if task is None:
        # Resilience only: local content is not the main generator.
        seen = {str(a.get("question_id")) for a in attempts}
        task = AdaptiveEngine.select_task(TASKS, grade, topic, level, seen) or AdaptiveEngine.select_task(TASKS, grade, topic, level, set())
        if task:
            st.warning("Жаңа тапсырманы автоматты құру аяқталмады. Дайын тапсырма көрсетілді.")
    if task:
        st.session_state.current_task = task
        st.session_state.adaptive_feedback = None
        st.session_state.adaptive_checked_id = None
        st.session_state.correction_mistake_id = mistake["id"] if mistake else None
    else:
        st.error("Жаңа тапсырма жасау мүмкін болмады. Интернет байланысын тексеріп, қайта көріңіз.")


def page_adaptive(user: dict[str, Any]) -> None:
    grade = int(user.get("grade") or 9)
    topics = ensure_student_topics(user)
    mastery = DB.get_mastery(user["id"], grade)
    states = DB.all_review_states(user["id"])
    auto = AdaptiveEngine.choose_topic(mastery, due_topics(states)) or topics[0]
    st.title("🎯 Адаптивті оқу")
    c1, c2 = st.columns([2,1])
    with c1:
        topic_choice = st.selectbox("Тақырып", ["Автоматты таңдау"] + topics)
        topic = auto if topic_choice == "Автоматты таңдау" else topic_choice
    with c2:
        score = current_topic_score(user["id"], grade, topic)
        recent = [a for a in DB.attempts(user["id"], 20) if a["topic"] == topic]
        level = AdaptiveEngine.recommended_level(score, recent)
        st.metric("Ұсынылған деңгей", level, f"меңгеру {score:.0f}%")
    st.caption(AdaptiveEngine.explanation(topic, score, level))

    if st.button("Жаңа ЖИ тапсырмасын құру", use_container_width=True):
        adaptive_new_task(user, topic)
        st.rerun()

    task = st.session_state.get("current_task")
    if not task or task.get("topic") != topic:
        st.info("Осы тақырыпқа жаңа тапсырма алу үшін жоғарыдағы батырманы басыңыз. Тапсырма оқушы профиліне сай құрылады.")
        return

    st.markdown(f"<div class='ai-card'><b>{escape(str(task.get('difficulty','B')))} деңгей • {escape(str(task['topic']))}</b><br><br>{escape(str(task['question']))}</div>", unsafe_allow_html=True)
    already_checked = st.session_state.get("adaptive_checked_id") == task.get("id")
    if already_checked:
        st.info("Бұл тапсырма бағаланды. Қайта тексеру үшін жаңа сұрақ алыңыз.")
    else:
      with st.form(f"adaptive_answer_{task.get('id','x')}"):
        if task.get("type") == "mcq" and task.get("options"):
            answer = st.radio("Жауабыңыз", task["options"], key=f"ans_{task.get('id')}")
        else:
            answer = st.text_input("Жауабыңыз (сан болса, өлшем бірлігін де жаза аласыз)")
        confidence = st.selectbox("Жауабыңызға қаншалықты сенімдісіз?", [1, 2, 3, 4, 5], index=2, key=f"confidence_{task.get('id')}")
        submit = st.form_submit_button("Тексеру", use_container_width=True)
    if already_checked:
        submit = False
    if submit:
        ok = evaluate_task(task, answer)
        err = None
        feedback = task.get("solution", "")
        if not ok:
            err = analyze_error(ai_client(), task["question"], answer, str(task.get("answer","")), str(task.get("solution","")), topic, task.get("error_hint"))
            DB.record_mistake(user["id"], topic, err["code"], err["description"])
            feedback = f"{err['label']}: {err['description']} Түзету: {err['correction']}"
        DB.log_attempt(
            student_id=user["id"], activity_type="adaptive", topic=topic, difficulty=task.get("difficulty"),
            question_id=task.get("id"), question_text=task["question"], student_answer=answer, correct_answer=task.get("answer"),
            is_correct=int(ok), confidence=confidence, score=100 if ok else 0, error_type=None if ok else err["code"], feedback=feedback,
        )
        if ok and st.session_state.get("correction_mistake_id"):
            DB.resolve_mistake(int(st.session_state.correction_mistake_id), user["id"])
            st.session_state.correction_mistake_id = None
        updated = DB.update_mastery(user["id"], grade, topic, ok)
        existing = DB.get_review_state(user["id"], topic)
        q = quality_from_result(ok, confidence, task.get("difficulty","B"))
        DB.upsert_review_state(user["id"], topic, next_state(existing, q))
        hint_by_error = {
            "FORMULA_ERROR": "Қолданған формулаңызды тексеріңіз.",
            "SI_ERROR": "Барлық шаманы SI жүйесіне ауыстырыңыз.",
            "UNIT_ERROR": "Жауаптың өлшем бірлігін тексеріңіз.",
            "CALCULATION_ERROR": "Арифметикалық амалдарды қайта есептеңіз.",
            "VECTOR_ERROR": "Бағыт пен таңбаны қайта қарап шығыңыз.",
            "GRAPH_ERROR": "График осьтерін және масштабыңызды тексеріңіз.",
            "READING_ERROR": "Шарттағы берілгендерді мұқият қайта оқыңыз.",
        }
        st.session_state.adaptive_feedback = {"ok":ok,"updated":updated,"solution":task.get("solution",""),
                                               "hint":hint_by_error.get((err or {}).get("code"),"Есептің шартын және тәсілді тексеріңіз.")}
        st.session_state.adaptive_checked_id = task.get("id")

    fb = st.session_state.get("adaptive_feedback")
    if fb:
        if fb["ok"]:
            st.success(f"Дұрыс. Жаңартылған меңгеру: {fb['updated']['score']:.0f}%")
            st.write(f"Шешуі: {fb['solution']}")
        else:
            st.error("Жауапта қате бар.")
            st.write("Қатені табуға нұсқау: " + fb["hint"])
            st.info("Ұқсас жаңа есепті шығарып көріңіз. Дұрыс жауап келесі бағалауда көрсетілмейді.")
        if st.button("Басқа тапсырмамен қайта тексеру", key=f"adaptive_next_{task.get('id')}", type="primary"):
            adaptive_new_task(user, topic)
            st.session_state.adaptive_checked_id = None
            st.rerun()


def evaluate_open_with_ai(question: str, rubric: str, answer: str) -> tuple[bool | None, str]:
    ai = ai_client()
    if ai.available:
        try:
            data = ai.json(
                "Сен PISA форматындағы физика тапсырмасын бағалайтын мұғалімсің. Рубрикадан шықпа.",
                f"Сұрақ: {question}\nРубрика: {rubric}\nОқушы жауабы: {answer}\nJSON: {{\"correct\":true/false,\"feedback\":\"қысқа түсіндірме\"}}",
            )
            return bool(data.get("correct")), str(data.get("feedback", ""))
        except Exception:
            pass
    return None, "ЖИ бағалауы қолжетімсіз. Жауап мұғалім тексеруін күтуде."


def _pisa_column_label(key: str) -> str:
    known = {
        "fuel": "Отын түрі",
        "fuel_type": "Отын түрі",
        "fuel_mass_kg": "Отын массасы, кг",
        "mass_kg": "Масса, кг",
        "specific_heat_of_combustion_mj_per_kg": "Меншікті жану жылуы, МДж/кг",
        "specific_heat_capacity_j_per_kg_c": "Меншікті жылу сыйымдылығы, Дж/(кг·°C)",
        "water_initial_temperature_c": "Судың бастапқы температурасы, °C",
        "water_final_temperature_c": "Судың соңғы температурасы, °C",
        "temperature_c": "Температура, °C",
        "time_s": "Уақыт, с",
        "distance_m": "Қашықтық, м",
        "speed_m_s": "Жылдамдық, м/с",
        "velocity_m_s": "Жылдамдық, м/с",
        "force_n": "Күш, Н",
        "energy_j": "Энергия, Дж",
        "power_w": "Қуат, Вт",
    }
    text = str(key or "").strip()
    if text.lower() in known:
        return known[text.lower()]
    return text.replace("_", " ").strip().capitalize() if "_" in text else text


def render_pisa_visual(task: dict[str, Any]) -> None:
    visual = task.get("visual")
    if not isinstance(visual, dict):
        return
    vtype = str(visual.get("type") or "").lower()
    title = str(visual.get("title") or "Көрнекі дерек")
    try:
        if vtype == "table" and isinstance(visual.get("rows"), list) and visual["rows"]:
            st.markdown(f"**{title}**")
            df = pd.DataFrame(visual["rows"])
            labels = visual.get("column_labels") if isinstance(visual.get("column_labels"), dict) else {}
            rename = {str(c): str(labels.get(str(c)) or _pisa_column_label(str(c))) for c in df.columns}
            st.dataframe(df.rename(columns=rename), hide_index=True, use_container_width=True)
        elif vtype in {"bar", "line"}:
            x = visual.get("x") or []
            y = visual.get("y") or []
            if isinstance(x, list) and isinstance(y, list) and len(x) == len(y) and x:
                x_label = str(visual.get("x_label") or "Көрсеткіш")
                y_label = str(visual.get("y_label") or "Мән")
                df = pd.DataFrame({x_label: x, y_label: y})
                if vtype == "bar":
                    safe_bar_chart(df, x=x_label, y=y_label, title=title)
                else:
                    safe_line_chart(df, x=x_label, y=y_label, title=title)
        elif vtype == "diagram":
            spec = visual.get("diagram") if isinstance(visual.get("diagram"), dict) else visual
            spec = _repair_pisa_diagram_spec(task, visual, dict(spec) if isinstance(spec, dict) else {})
            diagram_title = str(visual.get("title") or task.get("title") or task.get("topic") or "Физикалық сызба")
            svg = render_physics_diagram_svg(spec, title=diagram_title).decode("utf-8")
            render_svg(svg, height=500)
            # Keep explanatory prose outside the SVG so it never gets clipped inside the image.
            caption = str((spec or {}).get("caption") or visual.get("caption") or "").strip()
            if caption:
                st.markdown(normalize_math(caption))
        elif vtype == "image" and visual.get("image_b64"):
            st.markdown(f"**{title}**")
            st.image(base64.b64decode(str(visual["image_b64"])), use_container_width=True)
    except Exception:
        st.caption("Көрнекі деректі көрсету аяқталмады.")


def ensure_pisa_visual_image(task: dict[str, Any]) -> dict[str, Any]:
    """Use generated illustration for automatic pictorial visuals; retain explicit schematics."""
    visual = task.get("visual")
    if not isinstance(visual, dict):
        return task
    vtype = str(visual.get("type") or "").lower()
    if vtype == "diagram" and task.get("visual_mode") != "diagram" and ai_client().available:
        visual = {"type": "image", "title": str(task.get("title") or "Физикалық көрнекілік"),
                  "prompt": f"Мектеп оқулығына арналған шынайы физикалық иллюстрация. Тақырып: {task.get('topic')}. Жағдаят: {str(task.get('scenario') or '')[:900]}. Физикаға сай көрінсін."}
        task["visual"] = visual
        vtype = "image"
    if vtype != "image" or visual.get("image_b64") or not visual.get("prompt") or not ai_client().available:
        return task
    try:
        prompt = str(visual.get("prompt") or "").strip()
        prompt += "\nСуреттің ішінде мәтін, формула, әріп, белгі немесе сутаңба жазба."
        blob = ai_client().image(prompt, size="1024x1024")
        visual["image_b64"] = base64.b64encode(blob).decode("ascii")
        task["visual"] = visual
    except Exception:
        st.warning("Суретті құрастыру аяқталмады. Мәтіндегі деректермен тапсырманы орындауға болады.")
    return task

def task_display_title(title: Any) -> str:
    """Show legacy and generated titles without the internal task category name."""
    cleaned = re.sub(r"(?i)\bPISA\b", "", str(title or ""))
    return cleaned.strip(" \t:—–-") or "Тапсырма"


def render_pisa_task(task: dict[str, Any]) -> None:
    meta_html = f"""
    <div class="pisa-meta-grid">
      <div class="pisa-meta-card"><div class="pisa-meta-label">Контекст</div><div class="pisa-meta-value">{escape(str(task.get('context_category') or '—'))}</div></div>
      <div class="pisa-meta-card"><div class="pisa-meta-label">Құзыреттілік</div><div class="pisa-meta-value">{escape(str(task.get('competency') or '—'))}</div></div>
      <div class="pisa-meta-card"><div class="pisa-meta-label">Деңгей</div><div class="pisa-meta-value">{escape(str(task.get('pisa_level') or '—'))}</div></div>
    </div>
    """
    st.markdown(meta_html, unsafe_allow_html=True)
    st.subheader(task_display_title(task.get("title")))
    scenario = str(task.get("scenario") or "")
    if scenario:
        with st.container(border=True):
            render_rich_text(scenario)
    render_pisa_visual(task)


def page_pisa(user: dict[str, Any]) -> None:
    grade = int(user.get("grade") or 9)
    page_header("Тапсырмалар", "Өмірлік жағдаяттар арқылы тапсырмаларды орындаңыз.", "ЗЕРТТЕ • ТАЛДА • ДӘЛЕЛДЕ")
    teacher_tab, practice_tab = st.tabs(["Мұғалім берген тапсырмалар", "Жеке тапсырмалар"])

    with teacher_tab:
        assigned = DB.student_pisa_assignments(user["id"])
        if not assigned:
            st.info("Мұғалім сізге тапсырма әлі жібермеген.")
        else:
            selected = st.selectbox(
                "Тапсырманы таңдаңыз",
                range(len(assigned)),
                format_func=lambda i: f"{assigned[i]['class_name']} · {task_display_title(assigned[i]['title'])}",
                key="student_teacher_pisa_select",
            )
            row = assigned[selected]
            task = row.get("task") or {}
            st.caption(f"Тақырып: {row['topic']} · Жіберілген күні: {row['created_at'][:10]}")
            render_pisa_task(task)
            with st.form(f"teacher_pisa_form_{row['id']}"):
                answers: list[str] = []
                for i, qq in enumerate(task.get("questions") or [], 1):
                    st.markdown(f"**{i}.** {normalize_math(str(qq.get('q') or ''))}")
                    answers.append(st.text_area("Жауап", key=f"teacher_pisa_ans_{row['id']}_{i}", height=90))
                submit_assigned = st.form_submit_button("Жауаптарды жіберу", use_container_width=True, type="primary")
            if submit_assigned:
                results = []
                total = 0
                for i, (qq, ans) in enumerate(zip(task.get("questions") or [], answers), 1):
                    if qq.get("type") == "numeric":
                        fake = {"type": "numeric", "answer": qq.get("answer", ""), "tolerance": qq.get("tolerance", 0.02)}
                        ok = evaluate_task(fake, ans)
                        feedback = str(qq.get("rubric") or ("Дұрыс." if ok else "Есептеу жолын қайта тексеріңіз."))
                    else:
                        ok, feedback = evaluate_open_with_ai(str(qq.get("q") or ""), str(qq.get("rubric") or ""), ans)
                    total += int(ok is True)
                    correct_answer = str(qq.get("sample_answer") or qq.get("answer") or "")
                    DB.submit_pisa_response(row["id"], user["id"], i, str(qq.get("q") or ""), ans, correct_answer, ok, None if ok is None else (100 if ok else 0), feedback)
                    DB.log_attempt(
                        student_id=user["id"], activity_type="teacher_pisa", topic=row["topic"],
                        difficulty=f"PISA-{task.get('pisa_level', 4)}", question_id=f"TPISA-{row['id']}-{i}",
                        question_text=str(qq.get("q") or ""), student_answer=ans, correct_answer=correct_answer,
                        is_correct=None if ok is None else int(ok), confidence=3, score=None if ok is None else (100 if ok else 0),
                        error_type=None if ok is not False else "CONCEPT_ERROR", feedback=feedback,
                    )
                    if ok is not None:
                        DB.update_mastery(user["id"], grade, row["topic"], ok, weight=0.18)
                    results.append({"Сұрақ": i, "Нәтиже": "Мұғалім тексереді" if ok is None else ("Дұрыс" if ok else "Толықтыру керек"), "Кері байланыс": feedback})
                if results:
                    graded = sum(r["Нәтиже"] != "Мұғалім тексереді" for r in results)
                    st.metric("Бағаланған нәтиже", f"{total}/{graded}" if graded else "Мұғалім тексереді")
                    st.dataframe(pd.DataFrame(results), hide_index=True, use_container_width=True)

    with practice_tab:
        ensure_student_topics(user)
        topic = st.text_input("Тақырып", placeholder="Тақырыпты енгізіңіз...", key="pisa_topic_text")
        topic_clean = topic.strip()
        score = current_topic_score(user["id"], grade, topic_clean) if topic_clean else 0.0
        previous_titles = [a.get("question_text", "") for a in DB.attempts(user["id"], 100) if a.get("activity_type") == "pisa"]
        if st.button("Жаңа тапсырма құру", use_container_width=True, type="primary", key="student_personal_pisa_generate"):
            if not topic_clean:
                st.error("Тақырыпты енгізіңіз.")
            elif not ai_client().available:
                st.error("Жүйенің тапсырма құрастыру қызметі уақытша қолжетімсіз.")
            else:
                with st.spinner("Жаңа тапсырма құрастырылып жатыр..."):
                    pisa_status: dict[str, str] = {}
                    st.session_state.pisa_current = generate_pisa(ai_client(), grade, topic_clean, mastery=score, avoid_titles=previous_titles, status=pisa_status)
                    if st.session_state.pisa_current:
                        st.session_state.pisa_current = ensure_pisa_visual_image(st.session_state.pisa_current)
                if not st.session_state.pisa_current:
                    st.error(f"Тапсырманы құру мүмкін болмады. {pisa_status.get('reason', 'Қайта көріңіз.')}")
                else:
                    st.rerun()

        task = st.session_state.get("pisa_current")
        if not topic_clean:
            st.info("Жеке тапсырма құру үшін тақырыпты қолмен енгізіңіз.")
            return
        if not task or str(task.get("topic") or "").strip().lower() != topic_clean.lower():
            st.info("Жеке жұмыс үшін жаңа тапсырма құрыңыз.")
            return

        render_pisa_task(task)
        with st.form(f"pisa_{task.get('id','x')}"):
            answers = []
            for i, qq in enumerate(task["questions"], 1):
                st.markdown(f"**{i}.** {normalize_math(qq['q'])}")
                answers.append(st.text_area("Жауап", key=f"pisa_ans_{task.get('id')}_{i}", height=80))
            submit = st.form_submit_button("Жауаптарды бағалау", use_container_width=True)
        if submit:
            results = []
            total = 0
            for qq, ans in zip(task["questions"], answers):
                if qq.get("type") == "numeric":
                    fake = {"type":"numeric","answer":qq["answer"],"tolerance":qq.get("tolerance",0.02)}
                    ok = evaluate_task(fake, ans)
                    feedback = qq.get("rubric", "")
                else:
                    ok, feedback = evaluate_open_with_ai(qq["q"], qq.get("rubric",""), ans)
                total += int(ok is True)
                results.append({"Сұрақ":qq["q"],"Нәтиже":"Мұғалім тексереді" if ok is None else ("Дұрыс" if ok else "Толықтыру керек"),"Кері байланыс":feedback})
                DB.log_attempt(
                    student_id=user["id"], activity_type="pisa", topic=task["topic"], difficulty=f"PISA-{task.get('pisa_level',4)}", question_id=task.get("id"),
                    question_text=qq["q"], student_answer=ans, correct_answer=qq.get("sample_answer",qq.get("answer","")),
                    is_correct=None if ok is None else int(ok), confidence=3, score=None if ok is None else (100 if ok else 0), error_type=None if ok is not False else "CONCEPT_ERROR", feedback=feedback,
                )
                if ok is not None:
                    DB.update_mastery(user["id"], grade, task["topic"], ok, weight=0.18)
            graded = sum(r["Нәтиже"] != "Мұғалім тексереді" for r in results)
            st.metric("Тапсырма нәтижесі", f"{total}/{graded}" if graded else "Мұғалім тексереді")
            st.dataframe(pd.DataFrame(results), hide_index=True, use_container_width=True)
            st.session_state.pisa_current = None


def page_errors(user: dict[str, Any]) -> None:
    st.title("🔍 Қатемен интеллектуалды жұмыс")
    mistakes = DB.get_mistakes(user["id"], True)
    if not mistakes:
        st.success("Қайталанатын шешілмеген қате жоқ.")
        return
    df = pd.DataFrame(mistakes)
    err_df = df.assign(mistake_type=df["mistake_type"].map(error_label))
    if PLOTLY_AVAILABLE:
        st.plotly_chart(plotly_tnr(px.bar(err_df, x="frequency", y="topic", color="mistake_type", orientation="h", labels={"frequency":"Қайталану","topic":"Тақырып","mistake_type":"Қате түрі"})), use_container_width=True)
    else:
        safe_bar_chart(err_df.groupby("topic", as_index=False)["frequency"].sum(), x="frequency", y="topic", orientation="h")
    labels = [f"{m['topic']} — {error_label(m['mistake_type'])} ({m['frequency']} рет)" for m in mistakes]
    idx = st.selectbox("Қатені таңдаңыз", range(len(mistakes)), format_func=lambda i: labels[i])
    m = mistakes[idx]
    st.markdown(f"<div class='ai-card'><b>{escape(error_label(m['mistake_type']))}</b><br>{escape(str(m['description']))}<br><span class='small-muted'>Соңғы рет: {m['last_seen'][:16]}</span></div>", unsafe_allow_html=True)
    if st.button("Түзету тапсырмасын ашу", use_container_width=True):
        adaptive_new_task(user, m["topic"], m)
        st.info("Түзету тапсырмасы «Адаптивті оқу» бөлімінде дайындалды.")
    st.caption("Қате түзету тапсырмасын дұрыс орындағаннан кейін автоматты түрде жабылады.")


def _stream_words(text: str):
    """Streamlit-friendly incremental rendering without exposing internal events."""
    for part in re.split(r"(\s+)", text):
        if part:
            yield part


def _ensure_active_conversation(user: dict[str, Any]) -> int:
    key = f"active_conversation_{user['id']}"
    rows = DB.conversations(user["id"])
    existing_ids = {int(x["id"]) for x in rows}
    current = st.session_state.get(key)
    if current not in existing_ids:
        current = int(rows[0]["id"]) if rows else DB.create_conversation(user["id"], user["role"])
        st.session_state[key] = current
    return int(current)


def _artifact_card(item: dict[str, Any]) -> None:
    path = Path(str(item.get("path") or ""))
    if not path.is_file():
        return
    kind = str(item.get("type") or "file")
    labels = {"docx": "Құжат дайын", "pdf": "PDF дайын", "pptx": "Презентация дайын", "image": "Сурет дайын", "svg": "Сызба дайын"}
    mime = {"docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "pdf":"application/pdf", "pptx":"application/vnd.openxmlformats-officedocument.presentationml.presentation", "image":"image/png", "svg":"image/svg+xml"}.get(kind, "application/octet-stream")
    title = escape(str((item.get('metadata') or {}).get('title') or item.get('filename')))
    st.markdown(f"<div class='ai-card'><b>{escape(labels.get(kind, 'Материал дайын'))}</b><br><span class='small-muted'>{title}</span></div>", unsafe_allow_html=True)
    data = path.read_bytes()
    if kind == "svg":
        try:
            svg = data.decode("utf-8")
            render_svg(svg, height=520)
        except UnicodeDecodeError:
            pass
    elif kind == "image":
        st.image(data, use_container_width=True)
    st.download_button(f"{path.suffix.upper().lstrip('.')} жүктеу", data, file_name=str(item["filename"]), mime=mime, key=f"download_artifact_{item['id']}", use_container_width=True)


def page_ai_workspace(user: dict[str, Any]) -> None:
    teacher = user["role"] == "teacher"
    page_header(
        "Мұғалім ЖИ ассистенті" if teacher else "Оқушы ЖИ көмекшісі",
        "Мәтін, файл, сурет, есептеу және оқу материалдарын бір чатта қолданыңыз." if teacher else "Физиканы түсіндіріп, есептер мен суреттерді бірге талдайтын жеке оқу көмекшісі.",
        "БІРЫҢҒАЙ AI PHYSICS KZ ЖҰМЫС ОРТАСЫ" if teacher else "ЖЕКЕ ОҚУ КӨМЕКШІСІ",
    )
    active = _ensure_active_conversation(user)
    state_key = f"active_conversation_{user['id']}"
    left, chat = st.columns([1, 3], gap="medium")
    with left:
        if st.button("＋ Жаңа чат", use_container_width=True, type="primary", key=f"new_chat_{user['id']}"):
            st.session_state[state_key] = DB.create_conversation(user["id"], user["role"])
            st.rerun()
        rows = DB.conversations(user["id"])
        for row in rows:
            if st.button(str(row["title"]), key=f"open_conv_{row['id']}", use_container_width=True, disabled=int(row["id"]) == active):
                st.session_state[state_key] = int(row["id"]); st.rerun()
        current = DB.conversation(active, user["id"])
        with st.expander("Чатты басқару"):
            new_title = st.text_input("Чат атауы", value=str(current["title"]), key=f"rename_{active}")
            if st.button("Атауын сақтау", key=f"save_name_{active}", use_container_width=True):
                DB.rename_conversation(active, user["id"], new_title); st.rerun()
            confirm = st.checkbox("Жоюды растау", key=f"confirm_conv_{active}")
            if st.button("Чатты өшіру", key=f"delete_conv_{active}", disabled=not confirm, use_container_width=True):
                DB.delete_conversation(active, user["id"]); st.session_state.pop(state_key, None); st.rerun()

    with chat:
        history = DB.messages(active, user["id"], 100)
        for msg in history:
            with st.chat_message("assistant" if msg["sender"] == "assistant" else "user", avatar="⚛" if msg['sender'] == 'assistant' else "👤"):
                render_rich_text(msg["text"])

        for item in DB.generated_files(active, user["id"]):
            _artifact_card(item)

        response_slot = st.container()
        uploads = st.file_uploader(
            "Файл немесе сурет тіркеу",
            type=["pdf","docx","pptx","xlsx","csv","txt","md","png","jpg","jpeg","webp"],
            accept_multiple_files=True,
            key=f"assistant_upload_{active}",
            help="Файлды осы жерге сүйреп әкелуге немесе таңдауға болады.",
        )
        placeholder = "Мұғалім ЖИ ассистентіне жазыңыз..." if teacher else "ЖИ көмекшісіне жазыңыз..."
        prompt = st.chat_input(placeholder, key=f"assistant_input_{active}")
        if prompt:
            message_id = DB.add_message(active, user["id"], "user", prompt)
            with response_slot:
                with st.chat_message('user', avatar='👤'):
                    render_rich_text(prompt)
            attachment_texts: list[str] = []
            image_bytes = None; image_mime = "image/jpeg"
            try:
                for up in uploads or []:
                    data = up.getvalue()
                    display, saved = save_upload(UPLOAD_DIR / "assistant", up.name, data, up.type or "application/octet-stream", AI_CONFIG.max_attachment_mb)
                    DB.add_attachment(message_id, user["id"], display, up.type or "application/octet-stream", str(saved), len(data))
                    if (up.type or "").startswith("image/") and image_bytes is None:
                        image_bytes, image_mime = data, up.type
                    else:
                        try:
                            attachment_texts.append(f"{display}:\n{extract_text(display, data)[:18000]}")
                        except Exception:
                            attachment_texts.append(f"{display}: файл тіркелді; мәтін қабаты табылмады.")
                with response_slot, st.chat_message("assistant", avatar="⚛"):
                    status = st.empty()
                    status.caption("Материал талданып жатыр...")
                    core = AICore(DB, ai_client(), GENERATED_DIR)
                    result = core.run(user, active, prompt, "\n\n".join(attachment_texts), image_bytes is not None, image_bytes, image_mime)
                    status.empty()
                    render_rich_text(result.text)
                DB.add_message(active, user["id"], "assistant", result.text)
                st.session_state[f"retry_prompt_{active}"] = None
            except Exception:
                friendly = "Сұрауды толық орындау мүмкін болмады. Қайта орындау батырмасын қолданыңыз; тіркелген тарих жоғалмайды."
                DB.add_message(active, user["id"], "assistant", friendly, "failed")
                st.session_state[f"retry_prompt_{active}"] = prompt
            st.rerun()

        retry = st.session_state.get(f"retry_prompt_{active}")
        if retry and st.button("Қайта орындау", key=f"retry_{active}", use_container_width=True):
            st.session_state[f"retry_prompt_{active}"] = None
            try:
                result = AICore(DB, ai_client(), GENERATED_DIR).run(user, active, retry)
                DB.add_message(active, user["id"], "assistant", result.text)
            except Exception:
                DB.add_message(active, user["id"], "assistant", "Қызметке қосылу сәтсіз болды. Кейінірек қайта көріңіз.", "failed")
            st.rerun()


def page_tutor(user: dict[str, Any]) -> None:
    page_ai_workspace(user)
    return
    grade = int(user.get("grade") or 9)
    ensure_student_topics(user)
    page_header("ЖИ мұғалім", "Физиканы бірге түсінеміз. Кез келген сұрағыңды қой!", "ӘРҚАШАН СЕНІҢ ҚАСЫҢДА")
    st.markdown("<div class='status-pill'>● ЖИ МҰҒАЛІМ ОНЛАЙН</div>", unsafe_allow_html=True)
    history = DB.chat_history(user["id"], 30)
    for msg in history:
        with st.chat_message(msg["role"]):
            render_rich_text(msg["content"])
    question = st.chat_input("Физикадан сұрағыңызды жазыңыз...")
    if question:
        DB.add_chat(user["id"], "user", question)
        chunks = DB.accessible_chunks_for_student(user["id"])
        found = retrieve(question, chunks, top_k=4)
        rag_context = format_context(found)
        mastery = DB.get_mastery(user["id"], grade)
        mistakes = DB.get_mistakes(user["id"])
        recent = DB.attempts(user["id"], 12)
        try:
            reply = tutor_reply(ai_client(), user, mastery, mistakes, recent, question, rag_context)
        except Exception:
            reply = "Сұрауды орындау уақытша аяқталмады. Бірнеше секундтан кейін қайта жіберіп көріңіз."
        DB.add_chat(user["id"], "assistant", reply)
        st.rerun()
    if history and st.button("Чат тарихын тазарту"):
        DB.clear_chat(user["id"])
        st.rerun()


def page_progress(user: dict[str, Any]) -> None:
    grade = int(user.get("grade") or 9)
    mastery = DB.get_mastery(user["id"], grade)
    mistakes = DB.get_mistakes(user["id"])
    diagnostics = DB.diagnostic_history(user["id"])
    attempts = DB.attempts(user["id"], 500)
    path = build_learning_path(mastery, mistakes)
    st.title("📈 Менің прогресім")
    metric_row(user["id"], grade)
    c1, c2 = st.columns(2)
    with c1:
        measured_mastery = [r for r in mastery if int(r.get("attempts") or 0) > 0]
        if measured_mastery:
            df = pd.DataFrame(measured_mastery)
            safe_bar_chart(df, x="topic", y="score", range_max=100)
        else:
            st.info("Прогресс графигі тапсырмалар орындалғаннан кейін көрсетіледі.")
    with c2:
        if diagnostics:
            ddf = pd.DataFrame(list(reversed(diagnostics)))
            ddf["Кезең"] = range(1, len(ddf)+1)
            safe_line_chart(ddf, x="Кезең", y="percent", range_max=100)
        else:
            st.info("Динамика үшін кемінде бір диагностика орындаңыз.")
    st.subheader("Жеке оқу траекториясы")
    pairs = paired_diagnostics(diagnostics)
    if pairs:
        st.subheader("Бастапқы және қорытынды диагностика")
        st.dataframe(pd.DataFrame(pairs), hide_index=True, use_container_width=True)
    st.dataframe(pd.DataFrame(path).rename(columns={"topic":"Тақырып","score":"Меңгеру","action":"Ұсынылатын әрекет"}), hide_index=True, use_container_width=True)
    st.subheader("Есепті экспорттау")
    docx = build_student_docx(user, mastery, mistakes, diagnostics, path)
    pdf = build_student_pdf(user, mastery, mistakes)
    d1, d2 = st.columns(2)
    d1.download_button("Word есебі", docx, file_name=f"AI_Physics_{user['username']}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
    d2.download_button("PDF есебі", pdf, file_name=f"AI_Physics_{user['username']}.pdf", mime="application/pdf", use_container_width=True)


def page_profile(user: dict[str, Any]) -> None:
    st.title("👤 Профиль")
    st.write(f"Аты-жөні: **{user['full_name']}**")
    st.write(f"Логин: **{user['username']}**")
    pc1, pc2 = st.columns([2,1])
    grade = pc1.selectbox("Сынып", SUPPORTED_GRADES, index=SUPPORTED_GRADES.index(int(user.get("grade") or 9)))
    current_letter = user.get("class_letter") or CLASS_LETTERS[0]
    letter_index = CLASS_LETTERS.index(current_letter) if current_letter in CLASS_LETTERS else 0
    class_letter = pc2.selectbox("Әріп", CLASS_LETTERS, index=letter_index)
    if st.button("Сыныпты сақтау"):
        DB.update_class_profile(user["id"], grade, class_letter)
        refresh_user()
        st.success(f"Сақталды: {grade}{class_letter}.")
    st.subheader("Сыныпқа қосылу")
    code = st.text_input("Мұғалім берген сынып коды")
    if st.button("Сыныпқа қосылу") and code.strip():
        try:
            name = DB.join_class(user["id"], code)
            st.success(f"{name} сыныбына қосылдыңыз.")
        except Exception as e:
            st.error(str(e))
    classes = DB.student_classes(user["id"])
    if classes:
        st.dataframe(pd.DataFrame([{"Сынып":c["name"],"Код":c["join_code"]} for c in classes]), hide_index=True, use_container_width=True)


def page_settings() -> None:
    st.title("⚙️ Баптаулар")
    st.write("Жүйе баптаулары серверде автоматты түрде басқарылады.")
    st.info("Оқушы мен мұғалімге техникалық кілттер немесе модель атаулары көрсетілмейді.")

def teacher_student_summary(student: dict[str, Any]) -> dict[str, Any]:
    grade = int(student.get("grade") or 9)
    DB.ensure_topics(student["id"], grade, topics_for_grade(grade))
    mastery = DB.get_mastery(student["id"], grade)
    measured = [r for r in mastery if int(r.get("attempts") or 0) > 0]
    avg = sum(float(r["score"]) for r in measured)/len(measured) if measured else None
    diags = DB.diagnostic_history(student["id"])
    return {
        "Оқушы": student["full_name"],
        "Сынып": f"{grade}{student.get('class_letter') or ''}",
        "Орташа меңгеру": round(avg,1) if avg is not None else None,
        "Соңғы диагностика": diags[0]["percent"] if diags else None,
        "Қате саны": sum(int(m["frequency"]) for m in DB.get_mistakes(student["id"])),
    }


def page_teacher_dashboard(user: dict[str, Any]) -> None:
    page_header("Мұғалім панелі", "Сынып нәтижелері, оқушы прогресі және қолдау қажет бағыттар бір жерде.", "АНАЛИТИКА ЖӘНЕ БАСҚАРУ")
    classes = DB.teacher_classes(user["id"])
    if not classes:
        st.info("Алдымен «Сыныптар» бөлімінде сынып құрыңыз.")
        return
    idx = st.selectbox("Сынып", range(len(classes)), format_func=lambda i: classes[i]['name'])
    cls = classes[idx]
    students = DB.class_students(cls["id"])
    if not students:
        st.markdown("<div class='empty-card'><h3>Бұл сыныпқа оқушы әлі қосылмаған</h3><p>Оқушыларға сынып кодын жіберіңіз. Қосылған соң нәтижелері осы жерде көрінеді.</p></div>", unsafe_allow_html=True)
        st.code(cls["join_code"], language=None)
        st.caption("Оқушы «Тіркелу» бетінен өз сыныбын таңдап, осы кодты енгізеді.")
        if st.button("Сыныпты басқару", type="primary"):
            go_to("Сыныптар"); st.rerun()
        st.subheader("Алғашқы қадамдар")
        a,b,c = st.columns(3)
        a.info("1. Сынып кодын оқушыларға жіберіңіз.")
        b.info("2. Сынып тапсырмасын дайындаңыз.")
        c.info("3. Тест нәтижесін осы жерден бақылаңыз.")
        return
    rows = [teacher_student_summary(s) for s in students]
    df = pd.DataFrame(rows)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Белсенді оқушы", len(students), cls["name"])
    mastery_vals = pd.to_numeric(df["Орташа меңгеру"], errors="coerce").dropna()
    c2.metric("Орташа нәтиже", f"{mastery_vals.mean():.0f}%" if len(mastery_vals) else "—", "нақты орындалған тапсырмалар")
    diag_vals = pd.to_numeric(df["Соңғы диагностика"], errors="coerce").dropna()
    c3.metric("Орташа диагностика", f"{diag_vals.mean():.0f}%" if len(diag_vals) else "—", "соңғы өлшем")
    support_count = int((mastery_vals < 50).sum()) if len(mastery_vals) else 0
    c4.metric("Қолдау қажет", support_count, "50%-дан төмен")
    test_rows=[]
    weak_topics=defaultdict(int)
    for assignment in DB.teacher_assignments(user["id"],cls["id"]):
        if assignment.get("delivery_mode") != "online_test":
            continue
        reports=DB.teacher_online_test_reports(assignment["id"],user["id"])
        scores=[]
        for report in reports:
            answers=report["answers"]
            if answers:
                scores.append(round(100*sum(int(r["is_correct"]) for r in answers)/len(answers)))
            for item in answers:
                if not item["is_correct"]:
                    weak_topics[str(item["task"].get("topic") or assignment["topic"])]+=1
        test_rows.append({"Тест":assignment["title"],"Тапсырғандар":len(reports),
                          "Орташа балл":f"{sum(scores)/len(scores):.0f}%" if scores else "—"})
    if test_rows:
        st.subheader("Соңғы тесттердің нәтижесі")
        left, right=st.columns([2,1])
        left.dataframe(pd.DataFrame(test_rows),hide_index=True,use_container_width=True)
        with right:
            st.markdown("#### Назар аударатын тақырыптар")
            if weak_topics:
                for topic, errors in sorted(weak_topics.items(),key=lambda x:-x[1])[:5]:
                    st.write(f"{topic} · {errors} қате")
            else:
                st.caption("Қателер әлі тіркелмеген.")
    st.dataframe(df, hide_index=True, use_container_width=True)

    student_idx = st.selectbox("Оқушыны ашу", range(len(students)), format_func=lambda i: students[i]["full_name"])
    s = students[student_idx]
    grade = int(s.get("grade") or 9)
    mastery = DB.get_mastery(s["id"], grade)
    mistakes = DB.get_mistakes(s["id"])
    diags = DB.diagnostic_history(s["id"])
    pairs = paired_diagnostics(diags)
    st.subheader("Білім сапасының салыстырмалы нәтижесі")
    if pairs:
        st.dataframe(pd.DataFrame(pairs), hide_index=True, use_container_width=True)
    else:
        st.info("Бұл оқушыда бір тақырып бойынша бастапқы және қорытынды диагностика әлі толық орындалмаған.")
    learning_path = build_learning_path(mastery, mistakes)
    report = build_student_docx(s, mastery, mistakes, diags, learning_path)
    st.download_button("Оқушының оқу есебін Word түрінде жүктеу", report,
                       file_name=f"learning_result_{s['id']}.docx",
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    left,right = st.columns(2)
    with left:
        measured_mastery = [r for r in mastery if int(r.get("attempts") or 0) > 0]
        if measured_mastery:
            mdf = pd.DataFrame(measured_mastery)
            safe_bar_chart(mdf, x="score", y="topic", orientation="h", range_max=100)
        else:
            st.info("Бұл оқушы бойынша меңгеру дерегі әлі жиналмаған.")
    with right:
        st.subheader("Қайталанатын қателер")
        if mistakes:
            mdf_err = pd.DataFrame(mistakes)[["topic","mistake_type","frequency","last_seen"]].copy()
            mdf_err["mistake_type"] = mdf_err["mistake_type"].map(error_label)
            mdf_err.columns = ["Тақырып", "Қате түрі", "Қайталану", "Соңғы рет"]
            st.dataframe(mdf_err, hide_index=True, use_container_width=True)
        else:
            st.success("Қайталанатын қате жоқ.")


def _short_time(value: str | None) -> str:
    if not value:
        return "—"
    return str(value)[:16].replace("T", " ")


def page_classes(user: dict[str, Any]) -> None:
    st.title("🏫 Сыныптар")
    with st.form("create_class"):
        cc1, cc2 = st.columns([2, 1])
        class_grade = cc1.selectbox("Сынып", SUPPORTED_GRADES, index=2, key="teacher_class_grade")
        class_letter = cc2.selectbox("Әріп", CLASS_LETTERS, index=0, key="teacher_class_letter")
        st.caption(f"Құрылатын сынып: {class_grade}{class_letter}")
        create = st.form_submit_button("Сынып құру", use_container_width=True, type="primary")
    if create:
        name = f"{class_grade}{class_letter}"
        cls = DB.create_class(user["id"], name)
        st.success(f"{name} сыныбы құрылды. Қосылу коды: {cls['join_code']}")

    classes = DB.teacher_classes(user["id"])
    if not classes:
        st.info("Сынып әлі құрылмаған.")
        return
    st.subheader("Менің сыныптарым")
    for c in classes:
        students = DB.class_student_overview(c["id"])
        with st.expander(f"{c['name']} · {len(students)} оқушы", expanded=True):
            a, b = st.columns(2)
            a.metric("Қосылу коды", c["join_code"])
            b.metric("Оқушы саны", len(students))
            if students:
                rows = []
                for x in students:
                    rows.append({
                        "Оқушының аты-жөні": x["full_name"],
                        "Тіркелген күні": _short_time(x.get("joined_at")),
                        "Жалпы әрекет": int(x.get("attempt_count") or 0),
                        "Сынып жұмысы": int(x.get("class_work_count") or 0),
                        "Өмірлік тапсырмалар": int(x.get("pisa_work_count") or 0),
                        "Соңғы белсенділік": _short_time(x.get("last_activity")),
                    })
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            else:
                st.caption("Бұл сыныпқа оқушы әлі тіркелмеген.")


def page_teacher_students(user: dict[str, Any]) -> None:
    page_header("Оқушылар", "Әр оқушының тапсырмаларын, жауаптарын, дәптер жұмыстарын және толық оқу тарихын бақылаңыз.", "ОҚУШЫ МОНИТОРИНГІ")
    classes = DB.teacher_classes(user["id"])
    if not classes:
        st.info("Алдымен сынып құрыңыз.")
        return
    ci = st.selectbox("Сынып", range(len(classes)), format_func=lambda i: classes[i]["name"], key="monitor_class")
    cls = classes[ci]
    overview = DB.class_student_overview(cls["id"])
    if not overview:
        st.info("Бұл сыныпқа оқушы әлі тіркелмеген.")
        return
    st.dataframe(pd.DataFrame([{
        "Оқушы": r["full_name"],
        "Тіркелді": _short_time(r.get("joined_at")),
        "Әрекет саны": int(r.get("attempt_count") or 0),
        "Сынып жұмысы": int(r.get("class_work_count") or 0),
        "Өмірлік тапсырмалар": int(r.get("pisa_work_count") or 0),
        "Соңғы белсенділік": _short_time(r.get("last_activity")),
    } for r in overview]), hide_index=True, use_container_width=True)

    si = st.selectbox("Оқушыны таңдаңыз", range(len(overview)), format_func=lambda i: overview[i]["full_name"], key="monitor_student")
    student = overview[si]
    st.subheader(student["full_name"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Сынып", cls["name"])
    c2.metric("Оқу әрекеті", int(student.get("attempt_count") or 0))
    c3.metric("Дәптер жұмысы", int(student.get("class_work_count") or 0))
    c4.metric("Өмірлік тапсырмалар", int(student.get("pisa_work_count") or 0))

    t1, t2, t3, t4 = st.tabs(["Барлық жауаптар", "Сынып тапсырмалары", "Өмірлік тапсырмалар", "Дәптер жұмыстары"])
    with t1:
        attempts = DB.student_activity_attempts(student["id"], 500)
        if attempts:
            rows = []
            for a in attempts:
                rows.append({
                    "Күні": _short_time(a.get("created_at")),
                    "Бөлім": a.get("activity_type"),
                    "Тақырып": a.get("topic"),
                    "Тапсырма": a.get("question_text"),
                    "Оқушы жауабы": a.get("student_answer"),
                    "Дұрыс жауап": a.get("correct_answer"),
                    "Нәтиже": "Мұғалім тексереді" if a.get("is_correct") is None else ("Дұрыс" if a.get("is_correct") else "Қате/толық емес"),
                    "Балл": a.get("score"),
                    "Кері байланыс": a.get("feedback"),
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            for attempt in attempts:
                if attempt.get("activity_type") != "pisa" or attempt.get("is_correct") is not None:
                    continue
                st.markdown(f"**Жеке тапсырма · {attempt.get('topic')}**: {attempt.get('question_text')}")
                st.write(f"Оқушы жауабы: {attempt.get('student_answer') or '—'}")
                with st.form(f"grade_personal_{attempt['id']}"):
                    verdict = st.radio("Баға", ["Дұрыс", "Толықтыру керек"], horizontal=True, key=f"personal_verdict_{attempt['id']}")
                    note = st.text_input("Түсіндірме", key=f"personal_note_{attempt['id']}")
                    if st.form_submit_button("Бағаны сақтау"):
                        if DB.grade_personal_pisa_attempt(attempt["id"], user["id"], verdict == "Дұрыс", note):
                            st.success("Баға сақталды.")
                            st.rerun()
        else:
            st.caption("Әзірге оқу әрекеті жоқ.")
    with t2:
        hist = DB.student_assignment_history(student["id"])
        if not hist:
            st.caption("Сынып тапсырмасына жауап тарихы жоқ.")
        for h in hist:
            task = h.get("task") or {}
            with st.expander(f"{h['assignment_title']} · {h['position']}-тапсырма · {_short_time(h.get('submitted_at'))}"):
                st.markdown(f"**Тапсырма:** {normalize_math(str(task.get('question') or ''))}")
                st.write(f"Оқушы жауабы: {h.get('student_answer') or '—'}")
                st.write(f"Дұрыс жауап: {task.get('answer') or 'Мұғалім бағалайды'}")
                st.write(f"Нәтиже: {'Дұрыс' if h.get('is_correct') else 'Қате/толық емес'} · Балл: {float(h.get('score') or 0):.0f}%")
                if h.get("feedback"):
                    st.info(h["feedback"])
    with t3:
        ph = DB.student_teacher_pisa_history(student["id"])
        if not ph:
            st.caption("Мұғалім берген тапсырмалар бойынша жауап жоқ.")
        else:
            st.dataframe(pd.DataFrame([{
                "Күні": _short_time(x.get("submitted_at")),
                "Тапсырма": task_display_title(x.get("title")),
                "Тақырып": x.get("topic"),
                "Сұрақ": x.get("question_text"),
                "Оқушы жауабы": x.get("student_answer"),
                "Дұрыс/үлгі жауап": x.get("correct_answer"),
                "Нәтиже": "Мұғалім тексереді" if x.get("is_correct") is None else ("Дұрыс" if x.get("is_correct") else "Толықтыру керек"),
                "Кері байланыс": x.get("feedback"),
            } for x in ph]), hide_index=True, use_container_width=True)
    with t4:
        works = DB.student_work_history(student["id"])
        if not works:
            st.caption("Дәптер жұмысының суреттері жоқ.")
        for w in works:
            st.markdown(f"**{w['assignment_title']}** · {w['topic']} · {_short_time(w.get('submitted_at'))} · {float(w.get('score') or 0):.0f}%")
            st.image(w["image_data"], caption=f"{student['full_name']} — дәптер жұмысы", width=560)
            if w.get("ai_feedback"):
                st.info(w["ai_feedback"])
            st.divider()


def page_materials(user: dict[str, Any]) -> None:
    st.title("📚 Оқу материалдары")
    st.write("Материал нақты сыныптарға бекітіледі. Оқушының цифрлық көмекшісі тек өзі кіретін сыныптарға рұқсат етілген материалдарды пайдаланады.")
    classes = DB.teacher_classes(user["id"])
    upload = st.file_uploader("Оқу материалы", type=["pdf","docx","txt","md","csv"])
    title = st.text_input("Материал атауы")
    selected_class_ids = st.multiselect(
        "Материал қолжетімді болатын сыныптар",
        options=[int(c["id"]) for c in classes],
        format_func=lambda cid: next((c["name"] for c in classes if int(c["id"]) == int(cid)), str(cid)),
    )
    if st.button("Индекстеу", disabled=upload is None):
        try:
            raw = upload.getvalue()
            text = extract_text(upload.name, raw)
            chunks = chunk_text(text)
            if not chunks:
                st.error("Файлдан мәтін алынбады. Егер PDF скан-кескін болса, мәтіндік PDF қолданыңыз.")
            else:
                did = DB.add_document(user["id"], upload.name, title.strip() or upload.name, chunks)
                DB.assign_document_to_classes(did, user["id"], selected_class_ids)
                st.success(f"Материал индекстелді: {len(chunks)} бөлік. Сынып саны: {len(selected_class_ids)}.")
        except Exception as e:
            st.error("Материалды өңдеу аяқталмады. Файлды тексеріп, қайта жүктеп көріңіз.")
    docs = DB.list_documents(user["id"])
    if docs:
        st.subheader("Жүктелген материалдар")
        for d in docs:
            assigned = DB.document_class_ids(d["id"], user["id"])
            assigned_names = [c["name"] for c in classes if int(c["id"]) in assigned]
            c1,c2 = st.columns([5,1])
            c1.write(f"**{d['title']}** — {d['filename']} ({d['created_at'][:10]}) · Сыныптар: {', '.join(assigned_names) if assigned_names else 'бекітілмеген'}")
            if c2.button("Жою", key=f"del_doc_{d['id']}"):
                DB.delete_document(d["id"], user["id"])
                st.rerun()
            with st.expander(f"Сыныптарға қолжетімділікті өзгерту · {d['title']}"):
                mapped = st.multiselect(
                    "Сыныптар",
                    options=[int(c["id"]) for c in classes],
                    default=assigned,
                    format_func=lambda cid: next((c["name"] for c in classes if int(c["id"]) == int(cid)), str(cid)),
                    key=f"doc_classes_{d['id']}",
                )
                if st.button("Бекітуді сақтау", key=f"save_doc_classes_{d['id']}"):
                    DB.assign_document_to_classes(d["id"], user["id"], mapped)
                    st.success("Материал қолжетімділігі жаңартылды.")
                    st.rerun()


def page_student_assignments(user: dict[str, Any]) -> None:
    st.title("📝 Сынып тапсырмалары")
    previous_tests=DB.student_online_test_reports(user["id"])
    if previous_tests:
        with st.expander("Тапсырылған тесттерім және есептерім"):
            selected_report=st.selectbox("Есепті таңдаңыз",range(len(previous_tests)),
                format_func=lambda i:f"{previous_tests[i]['title']} · {previous_tests[i]['finished_at'][:10]}")
            render_online_test_report(previous_tests[selected_report], instance="history")
    rows = DB.student_assignments(user["id"])
    if not rows:
        st.info("Сізге жіберілген белсенді тапсырма жоқ.")
        return
    idx = st.selectbox("Тапсырманы таңдаңыз", range(len(rows)), format_func=lambda i: f"{rows[i]['class_name']} · {rows[i]['title']}")
    assignment = rows[idx]
    items = DB.assignment_items(assignment["id"])
    st.caption(f"Тақырып: {assignment['topic']} · Деңгей: {assignment['difficulty']}")
    if assignment.get("instructions"):
        st.info(assignment["instructions"])
    if assignment.get("delivery_mode") == "online_test":
        page_online_test(user, assignment, items)
        return
    st.markdown("### Дәптерге орындаңыз")
    for n, item in enumerate(items, 1):
        task = item["task"]
        st.markdown(f"**{n}.** {normalize_math(task.get('question',''))}")
        descriptors = clean_descriptors(task.get("descriptors"))
        if descriptors:
            st.caption("Дескрипторлар: " + "; ".join(
                f"{d['description']} — {d['points']} балл" for d in descriptors))
    st.caption("Барлық есепті дәптерге шығарып, анық фотоға түсіріңіз. Жүктелген сурет тексеріліп, мұғалімге жіберіледі.")
    upload = st.file_uploader("Дәптер жұмысының суреті", type=["jpg", "jpeg", "png"], key=f"work_img_{assignment['id']}")
    if upload is not None:
        st.image(upload.getvalue(), caption="Жүктелген жұмыс", width=520)
    if st.button("Сканерлеу, тексеру және мұғалімге жіберу", use_container_width=True, type="primary", disabled=upload is None):
        with st.spinner("Дәптер жұмысы тексеріліп жатыр..."):
            result = analyze_notebook_submission(ai_client(), assignment, items, upload.getvalue(), upload.type or "image/jpeg")
        DB.save_assignment_work(user["id"], assignment["id"], upload.getvalue(), upload.type or "image/jpeg", result["feedback"], result["score"])
        for row in result.get("answers") or []:
            qidx = int(row["question_index"]) - 1
            if 0 <= qidx < len(items):
                item = items[qidx]
                DB.submit_assignment_item(
                    user["id"], assignment["id"], item["id"], row.get("student_answer", ""),
                    bool(row.get("correct")), float(row.get("score") or 0), str(row.get("feedback") or ""),
                )
        st.success(f"Жұмыс мұғалімге жіберілді. Нәтиже: {result['score']:.0f}%" if result.get("graded", bool(result.get("answers")))
                   else "Жұмыс мұғалімге жіберілді. Бағалауды мұғалім аяқтайды.")
        st.info(result["feedback"])


def render_online_test_report(report: dict[str, Any], *, teacher: bool = False, instance: str = "current") -> None:
    rows = report.get("answers") or []
    total = len(rows)
    correct = sum(int(row["is_correct"]) for row in rows)
    a, b, c = st.columns(3)
    a.metric("Дұрыс", f"{correct}/{total} ({correct / total * 100:.0f}%)" if total else "0/0")
    b.metric("Қате", total - correct)
    c.metric("Жұмсаған уақыт", elapsed_label(sum(int(r["duration_seconds"]) for r in rows)))
    focus = focus_recommendations(rows, str(report.get("topic") or ""))
    if focus:
        st.info("Көңіл бөлу керек: " + "; ".join(focus))
    elif rows:
        st.success("Барлық сұраққа дұрыс жауап бердіңіз.")
    st.dataframe(pd.DataFrame([{"№":r["position"],"Сұрақ":r["task"].get("question",""),
        "Нәтиже":"Дұрыс" if r["is_correct"] else "Қате", "Уақыт (с)":r["duration_seconds"]} for r in rows]),
        hide_index=True,use_container_width=True)
    csv_rows = pd.DataFrame([{"Сұрақ":r["position"],"Тақырып":r["task"].get("topic") or report["topic"],
        "Сұрақ мәтіні":r["task"].get("question",""),"Оқушы жауабы":r["answer"],
        "Дұрыс жауап":r["task"].get("answer") or "", "Шешуі":r["task"].get("solution") or "",
        "Кері байланыс":question_feedback(r),
        "Нәтиже":"Дұрыс" if r["is_correct"] else "Қате","Уақыт (с)":r["duration_seconds"]} for r in rows])
    st.markdown("#### Әр сұрақ бойынша кері байланыс")
    for row in rows:
        task = row.get("task") or {}
        result_label = "Дұрыс" if row["is_correct"] else "Қате"
        with st.expander(f"{row['position']}-сұрақ · {result_label} · {elapsed_label(row['duration_seconds'])}",
                         expanded=not teacher and not row["is_correct"] and total <= 8):
            st.write("Сұрақ:", task.get("question") or "—")
            st.write("Сіздің жауабыңыз:" if not teacher else "Оқушы жауабы:", row.get("answer") or "—")
            st.write("Дұрыс жауап:", task.get("answer") or "—")
            if task.get("solution"):
                st.write("Шешуі:", task["solution"])
            st.write("Кері байланыс:", question_feedback(row))
            if teacher and row.get("video_data"):
                st.video(bytes(row["video_data"]), format=row["video_mime"])
    st.download_button("Есепті CSV түрінде жүктеу",csv_rows.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"test_esep_{report['assignment_id']}_{report['student_id']}.csv",mime="text/csv",
                       key=f"test_csv_{report['id']}_{'t' if teacher else 's'}_{instance}")


def page_online_test(user: dict[str, Any], assignment: dict[str, Any], items: list[dict[str, Any]]) -> None:
    st.subheader("Онлайн тест")
    st.caption("Камераға тест алдында бір рет рұқсат беріңіз. Әр сұрақта жазба өзі басталып, жауап сақталғанда тоқтайды. Жазбалар бөлек сақталады.")
    run = DB.online_test_report(assignment["id"],user["id"])
    if run and run["finished_at"]:
        st.success("Тест тапсырылды. Сіздің есебіңіз:")
        render_online_test_report(run)
        return
    if not run:
        permission = camera_recorder(mode="permission",key=f"camera_permission_{assignment['id']}_{user['id']}",default=None)
        if isinstance(permission,dict) and permission.get("error"):
            st.error(str(permission["error"]))
        if st.button("Тестті бастау",type="primary",key=f"start_test_{assignment['id']}",
                     disabled=not (isinstance(permission,dict) and permission.get("ready") is True)):
            DB.start_online_test(assignment["id"],user["id"])
            st.rerun()
        return
    done = {r["item_id"] for r in run["answers"]}
    remaining = [item for item in items if item["id"] not in done]
    if not remaining:
        if st.button("Тестті аяқтап, есепті көру",type="primary",key=f"finish_test_{assignment['id']}"):
            DB.finish_online_test(assignment["id"],user["id"])
            st.rerun()
        return
    item=remaining[0]
    task=item["task"]
    choices=online_test_choices(task)
    if not choices:
        st.error("Бұл сұраққа төрт жауап нұсқасы енгізілмеген. Мұғалім тапсырманы өңдеуі керек.")
        return
    timer_key=f"test_question_started_{run['id']}_{item['id']}"
    st.session_state.setdefault(timer_key,time.time())
    st.progress(len(done)/max(1,len(items)),text=f"{len(done)+1}/{len(items)}-сұрақ")
    st.markdown(f"### {item['position']}. {normalize_math(str(task.get('question') or ''))}")
    pending_key=f"test_pending_answer_{run['id']}_{item['id']}"
    pending_answer=st.session_state.get(pending_key)
    recording=camera_recorder(mode="record",stop=bool(pending_answer),
        key=f"camera_{run['id']}_{item['id']}",default=None)
    if pending_answer and isinstance(recording,dict) and recording.get("data"):
        try:
            video=base64.b64decode(recording["data"],validate=True)
            duration=max(1,min(3600,int(time.time()-st.session_state[timer_key])))
            DB.save_online_test_answer(assignment["id"],user["id"],item["id"],pending_answer,
                evaluate_task(task,pending_answer),duration,video,str(recording.get("mime") or ""))
            st.session_state.pop(pending_key,None)
            st.rerun()
        except (ValueError,binascii.Error,OverflowError) as err:
            st.session_state.pop(pending_key,None)
            st.error(f"Жауап сақталмады: {err}")
    if isinstance(recording,dict) and recording.get("error"):
        st.session_state.pop(pending_key,None)
        st.error(str(recording["error"]))
    answer=st.radio("Жауапты таңдаңыз",["Жауап таңдаңыз",*choices],key=f"test_answer_{run['id']}_{item['id']}")
    if answer=="Жауап таңдаңыз": answer=""
    if st.button("Жауапты сақтап, келесі сұраққа өту",type="primary",key=f"test_next_{run['id']}_{item['id']}",
                 disabled=bool(pending_answer)):
        if not answer.strip():
            st.error("Алдымен жауапты енгізіңіз.")
        elif isinstance(recording,dict) and recording.get("error"):
            st.error(str(recording["error"]))
        else:
            st.session_state[pending_key]=answer.strip()
            st.rerun()
    if pending_answer:
        st.info("Бейнежазба тоқтатылып, жауап сақталып жатыр...")


def _make_generated_tasks(grade: int, topic: str, level: str, count: int, instructions: str,
                          *, require_descriptors: bool = True) -> list[dict[str, Any]]:
    client = ai_client()
    if client.available:
        tasks = generate_assignment_tasks(client, grade, topic, level, int(count), instructions)
        if require_descriptors:
            for task in tasks:
                if not task.get("descriptors"):
                    task["descriptors"] = generate_descriptors(
                        client, grade, task["question"], task["answer"], task["solution"], instructions)
        return tasks
    return []


def edit_task_descriptors(descriptors: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    st.caption("ЖИ ұсынған дескрипторларды қарап, қажет болса мәтіні мен баллын түзетіңіз.")
    count = st.number_input("Дескриптор саны", min_value=1, max_value=8,
                            value=max(1, len(descriptors)), key=f"desc_count_{key}")
    edited = []
    for idx in range(int(count)):
        row = descriptors[idx] if idx < len(descriptors) else {}
        left, right = st.columns([5, 1])
        description = left.text_input(f"{idx+1}-дескриптор", value=str(row.get("description") or ""),
                                      key=f"desc_text_{key}_{idx}")
        points = right.number_input("Балл", min_value=1, max_value=10,
                                    value=int(row.get("points") or 1), key=f"desc_points_{key}_{idx}")
        edited.append({"description": description, "points": int(points)})
    st.caption(f"Жалпы балл: {sum(row['points'] for row in edited)}")
    return clean_descriptors(edited)


def page_teacher_assignments(user: dict[str, Any]) -> None:
    st.title("📤 Сынып тапсырмалары")
    st.caption("Жүйе құрастырған тапсырмалар алдымен мұғалімге көрсетіледі. Тек тексергеннен кейін сыныпқа жіберіледі.")
    classes = DB.teacher_classes(user["id"])
    if not classes:
        st.info("Алдымен «Сыныптар» бөлімінде сынып құрыңыз.")
        return
    class_index = st.selectbox("Сынып", range(len(classes)), format_func=lambda i: classes[i]["name"], key="asg_class")
    cls = classes[class_index]
    match = re.match(r"\s*(\d{1,2})", str(cls["name"]))
    grade = int(match.group(1)) if match else 9

    c1, c2, c3 = st.columns([2, 1, 1])
    topic = c1.text_input("Тақырып", placeholder="Тақырыпты енгізіңіз...", key="asg_topic_text")
    level = c2.selectbox("Деңгей", ["A", "B", "C"], index=1, key="asg_level")
    count = c3.selectbox("Саны", list(range(1, 31)), index=2, key="asg_count")
    delivery = st.radio("Оқушы қалай орындайды?", ["Дәптер жұмысы", "Онлайн тест"], horizontal=True, key="asg_delivery")
    mode = st.radio("Тапсырманы дайындау тәсілі", ["Жүйе құрастырсын", "Мұғалім өзі енгізеді"], horizontal=True)
    title = st.text_input("Тапсырма атауы", placeholder="Мысалы: Бірқалыпты үдемелі қозғалыс — сынып жұмысы")
    instructions = st.text_area("Оқу мақсаты / нақты талап", placeholder="Оқу мақсатын немесе орындалу талабын жазыңыз...")

    tasks_to_send: list[dict[str, Any]] = []
    if mode == "Жүйе құрастырсын":
        if st.button("Алдын ала тапсырмаларды құрастыру", use_container_width=True, key="draft_assignment_generate"):
            if not topic.strip():
                st.error("Тақырыпты енгізіңіз.")
            else:
                with st.spinner("Тапсырмалар құрастырылып жатыр..."):
                    made = _make_generated_tasks(grade, topic.strip(), level, int(count), instructions,
                                                 require_descriptors=delivery == "Дәптер жұмысы")
                if len(made) != int(count) or (delivery == "Дәптер жұмысы" and any(not t.get("descriptors") for t in made)):
                    st.error(f"{count} сұрақтың {len(made)}-і ғана дайындалды. Толық жиынтық жасау үшін қайта көріңіз.")
                else:
                    st.session_state.teacher_assignment_draft = {
                        "class_id": cls["id"], "topic": topic.strip(), "level": level, "tasks": made
                    }
                    st.rerun()
        draft = st.session_state.get("teacher_assignment_draft")
        if draft and int(draft.get("class_id", -1)) == int(cls["id"]):
            st.markdown("### Алдын ала қарау")
            edited = []
            for i, task in enumerate(draft.get("tasks") or [], 1):
                with st.expander(f"{i}-тапсырма", expanded=True):
                    q = st.text_area("Тапсырма мәтіні", value=str(task.get("question") or ""), key=f"draft_q_{cls['id']}_{task['id']}")
                    ans = st.text_input("Дұрыс жауап", value=str(task.get("answer") or ""), key=f"draft_a_{cls['id']}_{task['id']}")
                    sol = st.text_area("Шешуі", value=str(task.get("solution") or ""), key=f"draft_s_{cls['id']}_{task['id']}")
                    updated_task={**task, "question": q.strip(), "answer": ans.strip(), "solution": sol.strip()}
                    if delivery == "Онлайн тест":
                        options=online_test_choices(updated_task)
                        if options:
                            st.caption("Жауап нұсқалары: " + " · ".join(options))
                        else:
                            st.warning("Бұл сұраққа төрт жарамды жауап нұсқасы керек.")
                    else:
                        basis = [q.strip(), ans.strip(), sol.strip()]
                        if task.get("descriptor_basis") != basis:
                            updated_task["descriptors"] = []
                            st.warning("Тапсырма өзгерді. Дескрипторларды ЖИ арқылы қайта құрастырыңыз.")
                        if st.button("Дескрипторларды ЖИ құрастырсын", key=f"draft_desc_generate_{cls['id']}_{task['id']}"):
                            proposed = generate_descriptors(ai_client(), grade, *basis, instructions)
                            if proposed:
                                task["descriptors"] = proposed
                                task["descriptor_basis"] = basis
                                task["descriptor_revision"] = int(task.get("descriptor_revision") or 0) + 1
                                st.session_state.teacher_assignment_draft = draft
                                st.rerun()
                            st.error("Дескрипторлар құрастырылмады. ЖИ қызметін тексеріп, қайта көріңіз.")
                        if updated_task["descriptors"]:
                            updated_task["descriptors"] = edit_task_descriptors(
                                updated_task["descriptors"], f"draft_{cls['id']}_{task['id']}_{task.get('descriptor_revision', 0)}")
                    edited.append(updated_task)
            draft["tasks"] = edited
            st.session_state.teacher_assignment_draft = draft
            tasks_to_send = edited
    else:
        st.markdown("### Тапсырмаларды енгізу")
        for i in range(int(count)):
            with st.expander(f"{i+1}-тапсырма", expanded=True):
                q = st.text_area("Тапсырма мәтіні", key=f"manual_q_{i}", placeholder="Есептің немесе сұрақтың мәтінін жазыңыз...")
                ans = st.text_input("Дұрыс жауап (қажет болса)", key=f"manual_a_{i}")
                sol = st.text_area("Шешуі / бағалау нұсқаулығы (қажет болса)", key=f"manual_s_{i}")
                wrong = ([st.text_input(f"Қате жауап нұсқасы {n}",key=f"manual_wrong_{i}_{n}").strip()
                          for n in range(1,4)] if delivery == "Онлайн тест" else [])
                if q.strip():
                    manual_task = {"id": f"MANUAL-{i+1}", "question": q.strip(),
                        "type": "mcq" if delivery == "Онлайн тест" else "open", "answer": ans.strip(),
                        "options": [ans.strip(), *wrong] if any(wrong) else [], "solution": sol.strip()}
                    if delivery == "Дәптер жұмысы":
                        basis = [q.strip(), ans.strip(), sol.strip()]
                        state_key = f"manual_descriptors_{cls['id']}_{i}"
                        saved = st.session_state.get(state_key) or {}
                        if st.button("Дескрипторларды ЖИ құрастырсын", key=f"manual_desc_generate_{cls['id']}_{i}"):
                            proposed = generate_descriptors(ai_client(), grade, *basis, instructions)
                            if proposed:
                                st.session_state[state_key] = {"basis": basis, "descriptors": proposed,
                                                               "revision": int(saved.get("revision") or 0) + 1}
                                st.rerun()
                            st.error("Дескрипторлар құрастырылмады. ЖИ қызметін тексеріп, қайта көріңіз.")
                        if saved.get("basis") == basis and saved.get("descriptors"):
                            manual_task["descriptors"] = edit_task_descriptors(
                                saved["descriptors"], f"manual_{cls['id']}_{i}_{saved['revision']}")
                        else:
                            st.info("Алдымен ЖИ арқылы осы тапсырманың дескрипторларын құрастырыңыз.")
                    tasks_to_send.append(manual_task)

    if st.button("Сыныпқа жіберу", use_container_width=True, type="primary", key="assignment_send"):
        if not topic.strip():
            st.error("Тақырыпты енгізіңіз.")
        elif not tasks_to_send:
            st.error("Алдымен тапсырмаларды құрастырыңыз немесе қолмен енгізіңіз.")
        elif mode == "Жүйе құрастырсын" and len(tasks_to_send) != int(count):
            st.error(f"Жіберу үшін {count} сұрақ толық дайындалуы керек. Қайта құрастырыңыз.")
        elif delivery.startswith("Онлайн") and any(not str(t.get("answer") or "").strip() for t in tasks_to_send):
            st.error("Онлайн тест үшін әр сұрақтың дұрыс жауабын енгізіңіз.")
        elif delivery.startswith("Онлайн") and any(not online_test_choices(t) for t in tasks_to_send):
            st.error("Онлайн тесттің әр сұрағында төрт бөлек жауап нұсқасы болсын. Мәтіндік жауапқа үш қате нұсқаны енгізіңіз.")
        elif delivery == "Дәптер жұмысы" and any(not clean_descriptors(t.get("descriptors")) for t in tasks_to_send):
            st.error("Әр тапсырмаға ЖИ құрастырған дескрипторларды бекітіңіз.")
        else:
            assignment_title = title.strip() or f"{topic.strip()} — {level} деңгей"
            aid = DB.create_assignment(user["id"], cls["id"], assignment_title, topic.strip(), level, tasks_to_send, instructions=instructions)
            if delivery.startswith("Онлайн"):
                DB.set_assignment_delivery_mode(aid,user["id"],"online_test")
            st.session_state.teacher_assignment_draft = None
            st.success(f"Сынып тапсырмасы жіберілді. Тапсырма саны: {len(tasks_to_send)}.")
            st.rerun()

    st.subheader("Берілген сынып тапсырмалары")
    assignments = DB.teacher_assignments(user["id"], cls["id"])
    if not assignments:
        st.caption("Бұл сыныпқа тапсырма әлі жіберілмеген.")
        return
    for a in assignments:
        stats = DB.assignment_stats(a["id"], user["id"]) if a.get("delivery_mode") != "online_test" else None
        with st.expander(f"{a['title']} · {a['topic']} · {a['difficulty']} · {a['created_at'][:10]}"):
            if a.get("delivery_mode") == "online_test":
                reports = DB.teacher_online_test_reports(a["id"], user["id"])
                st.write(f"Онлайн тест · {a['item_count']} сұрақ · тапсырғандар: {len(reports)}")
                if reports:
                    for report in reports:
                        with st.expander(f"{report['full_name']} — толық есеп және бейнежазба"):
                            full = DB.online_test_report(a["id"],report["student_id"],user["id"],include_video=True)
                            render_online_test_report(full,teacher=True)
                else:
                    st.info("Оқушылар бұл тестті әлі тапсырған жоқ.")
            else:
                st.write(f"Тапсырма саны: {a['item_count']} · Жұмыс жібергендер: {stats['students_started']}/{stats['total_students']} · Орташа нәтиже: {stats['avg_score']:.0f}%")
            items = DB.assignment_items(a["id"])
            with st.expander("Тапсырмаларды, жауаптарды және шешулерді көру"):
                for i, item in enumerate(items, 1):
                    task = item["task"]
                    st.markdown(f"**{i}. {normalize_math(str(task.get('question') or ''))}**")
                    st.write(f"Дұрыс жауап: {task.get('answer') or '—'}")
                    if task.get("solution"):
                        st.markdown("**Шешуі:**")
                        render_rich_text(str(task.get("solution")))
                    descriptors = clean_descriptors(task.get("descriptors"))
                    if descriptors:
                        st.markdown("**Дескрипторлар:**")
                        for d in descriptors:
                            st.write(f"{d['description']} — {d['points']} балл")
                    st.divider()
            with st.expander("Тапсырманы өңдеу"):
                et = st.text_input("Атауы", value=a["title"], key=f"edit_title_{a['id']}")
                ep = st.text_input("Тақырып", value=a["topic"], key=f"edit_topic_{a['id']}")
                el = st.selectbox("Деңгей", ["A", "B", "C"], index=["A", "B", "C"].index(a["difficulty"]), key=f"edit_level_{a['id']}")
                ei = st.text_area("Оқу мақсаты / талап", value=a.get("instructions") or "", key=f"edit_instr_{a['id']}")
                if st.button("Негізгі мәліметтерді сақтау", key=f"save_meta_{a['id']}"):
                    DB.update_assignment_meta(a["id"], user["id"], et, ep, el, ei)
                    st.success("Өзгерістер сақталды.")
                    st.rerun()
                for i, item in enumerate(items, 1):
                    task = item["task"]
                    q = st.text_area(f"{i}-тапсырма мәтіні", value=str(task.get("question") or ""), key=f"edit_q_{item['id']}")
                    aa = st.text_input(f"{i}-тапсырма жауабы", value=str(task.get("answer") or ""), key=f"edit_a_{item['id']}")
                    ss = st.text_area(f"{i}-тапсырма шешуі", value=str(task.get("solution") or ""), key=f"edit_s_{item['id']}")
                    revised_options = []
                    if a.get("delivery_mode") == "online_test":
                        previous = task.get("options") if isinstance(task.get("options"), list) else []
                        distractors = [str(x) for x in previous if str(x) != str(task.get("answer") or "")][:3]
                        revised_options = [st.text_input(f"{i}-сұрақ: қате нұсқа {n}",
                            value=distractors[n-1] if len(distractors) >= n else "",
                            key=f"edit_wrong_{item['id']}_{n}").strip() for n in range(1,4)]
                    if st.button(f"{i}-тапсырманы сақтау", key=f"save_item_{item['id']}"):
                        updated={**task, "question": q.strip(), "answer": aa.strip(), "solution": ss.strip()}
                        if a.get("delivery_mode") == "online_test":
                            updated["options"] = [aa.strip(), *revised_options] if any(revised_options) else []
                            if any(revised_options):
                                updated["type"] = "mcq"
                            if not online_test_choices(updated):
                                st.error("Төрт бөлек жауап нұсқасын енгізіңіз немесе сандық дұрыс жауап үшін қате нұсқаларды бос қалдырыңыз.")
                                continue
                        DB.update_assignment_item(item["id"], a["id"], user["id"], updated)
                        st.success("Тапсырма жаңартылды.")
                        st.rerun()

            responses = DB.teacher_assignment_responses(a["id"], user["id"]) if a.get("delivery_mode") != "online_test" else []
            if responses:
                st.markdown("#### Оқушылардың жауаптары")
                for r in responses:
                    task = r.get("task") or {}
                    st.write(f"**{r['full_name']} · {r['position']}-тапсырма** — {_short_time(r.get('submitted_at'))}")
                    st.markdown("**Тапсырма:**")
                    render_rich_text(str(task.get("question") or ""))
                    st.write(f"Оқушы жауабы: {r.get('student_answer') or '—'}")
                    st.write(f"Дұрыс жауап: {task.get('answer') or '—'} · Нәтиже: {'Дұрыс' if r.get('is_correct') else 'Қате/толық емес'} · {float(r.get('score') or 0):.0f}%")
                    if r.get("feedback"):
                        st.info(r["feedback"])
            works = DB.teacher_assignment_work(a["id"], user["id"]) if a.get("delivery_mode") != "online_test" else []
            if works:
                st.markdown("#### Оқушылардың дәптер жұмыстары")
                for w in works:
                    st.write(f"**{w['full_name']}** · {_short_time(w.get('submitted_at'))} · Баға: {w['score']:.0f}%")
                    st.image(w["image_data"], caption=f"{w['full_name']} — жүктелген дәптер жұмысы", width=520)
                    if w.get("ai_feedback"):
                        st.info(w["ai_feedback"])
                    st.divider()
            elif a.get("delivery_mode") != "online_test":
                st.caption("Әзірге дәптер жұмысы жіберілмеген.")
            b1, b2 = st.columns(2)
            new_status = "closed" if a["status"] == "active" else "active"
            label = "Тапсырманы жабу" if new_status == "closed" else "Қайта ашу"
            if b1.button(label, key=f"asg_status_{a['id']}"):
                DB.set_assignment_status(a["id"], user["id"], new_status)
                st.rerun()
            confirm = b2.checkbox("Жоюды растау", key=f"confirm_del_{a['id']}")
            if b2.button("Тапсырманы жою", key=f"delete_asg_{a['id']}", disabled=not confirm):
                DB.delete_assignment(a["id"], user["id"])
                st.rerun()


def page_teacher_pisa(user: dict[str, Any]) -> None:
    page_header("Тапсырмалар", "Тапсырманы құрастырып, алдын ала қарап, сыныпқа жіберіңіз.", "МҰҒАЛІМ ЗЕРТХАНАСЫ")
    classes = DB.teacher_classes(user["id"])
    if not classes:
        st.info("Алдымен сынып құрыңыз.")
        return
    ci = st.selectbox("Сынып", range(len(classes)), format_func=lambda i: classes[i]["name"], key="teacher_pisa_class")
    cls = classes[ci]
    match = re.match(r"\s*(\d{1,2})", str(cls["name"]))
    grade = int(match.group(1)) if match else 9
    topic = st.text_input("Тақырып немесе еркін сұраныс", placeholder="Мысалы: 9-сыныпқа жылу алмасу туралы өмірмен байланысты тапсырма жаса", key="teacher_pisa_topic")
    goal = st.text_area("Қосымша талап (міндетті емес)", placeholder="Мысалы: оқушы графиктен дерек оқысын, 2-сұрақта есептеу болсын...")
    visual_label = st.selectbox(
        "Көрнекілік түрі",
        ["Автоматты — ЖИ өзі таңдасын", "Кесте", "Бағандық график", "Сызықтық график", "Физикалық схема", "Контекстік сурет", "Көрнекіліксіз"],
        help="Автоматты режимде ЖИ тапсырманың мағынасына қарай кесте, график, физикалық схема, контекстік сурет немесе көрнекіліксіз форматтың бірін өзі таңдайды.",
    )
    visual_map = {
        "Автоматты — ЖИ өзі таңдасын": "auto",
        "Кесте": "table",
        "Бағандық график": "bar",
        "Сызықтық график": "line",
        "Физикалық схема": "diagram",
        "Контекстік сурет": "image",
        "Көрнекіліксіз": "none",
    }
    if st.button("Тапсырма құрастыру", use_container_width=True, type="primary", key="teacher_pisa_generate"):
        # Never leave an older task visible under newly entered parameters if generation fails.
        st.session_state.teacher_pisa_draft = None
        if not topic.strip():
            st.error("Тақырыпты енгізіңіз.")
        elif not ai_client().available:
            st.error("Тапсырма құрастыру қызметі уақытша қолжетімсіз.")
        else:
            with st.spinner("Тапсырма құрастырылып жатыр..."):
                pisa_status: dict[str, str] = {}
                task = generate_pisa(ai_client(), grade, topic.strip(), learning_goal=goal, visual_preference=visual_map[visual_label], status=pisa_status)
                if task:
                    task = ensure_pisa_visual_image(task)
            if task:
                st.session_state.teacher_pisa_draft = {
                    "class_id": cls["id"],
                    "topic_input": topic.strip(),
                    "visual_preference": visual_map[visual_label],
                    "task": task,
                }
                st.rerun()
            else:
                st.error(f"Тапсырманы құрастыру мүмкін болмады. {pisa_status.get('reason', 'Қайта көріңіз.')}")

    draft = st.session_state.get("teacher_pisa_draft")
    if draft and int(draft.get("class_id", -1)) == int(cls["id"]):
        draft_topic = str(draft.get("topic_input") or (draft.get("task") or {}).get("topic") or "").strip()
        draft_visual = str(draft.get("visual_preference") or "").strip()
        current_visual = visual_map[visual_label]
        if (topic.strip() and draft_topic.casefold() != topic.strip().casefold()) or (draft_visual and draft_visual != current_visual):
            st.caption("Параметрлер өзгертілді. Жаңа тақырыпқа тапсырманы қайта құрастырыңыз.")
            draft = None
    if draft and int(draft.get("class_id", -1)) == int(cls["id"]):
        task = draft["task"]
        st.markdown("### Алдын ала қарау және өңдеу")
        task["title"] = st.text_input("Тапсырма атауы", value=task_display_title(task.get("title")), key="teacher_pisa_draft_title")
        task["scenario"] = st.text_area("Жағдаят", value=str(task.get("scenario") or ""), height=150, key="teacher_pisa_draft_scenario")
        selected_visual = str(task.get("visual_selected") or "").strip()
        if selected_visual:
            visual_names = {"table":"Кесте", "bar":"Бағандық график", "line":"Сызықтық график", "diagram":"Физикалық схема", "image":"Контекстік сурет", "none":"Көрнекіліксіз"}
            st.caption(f"ЖИ таңдаған көрнекілік: {visual_names.get(selected_visual, selected_visual)}")
        render_pisa_task(task)
        for i, q in enumerate(task.get("questions") or [], 1):
            with st.expander(f"{i}-сұрақ", expanded=True):
                q["q"] = st.text_area("Сұрақ мәтіні", value=str(q.get("q") or ""), key=f"tpq_q_{i}")
                if q.get("type") == "numeric":
                    q["answer"] = st.text_input("Дұрыс жауап", value=str(q.get("answer") or ""), key=f"tpq_a_{i}")
                q["sample_answer"] = st.text_area("Үлгі жауап", value=str(q.get("sample_answer") or ""), key=f"tpq_sample_{i}")
                q["rubric"] = st.text_area("Бағалау шарты", value=str(q.get("rubric") or ""), key=f"tpq_rubric_{i}")
        draft["task"] = task
        st.session_state.teacher_pisa_draft = draft
        if st.button("Тапсырманы сыныпқа жіберу", use_container_width=True, type="primary"):
            DB.create_pisa_assignment(user["id"], cls["id"], str(task.get("title") or topic), topic.strip() or str(task.get("topic") or "PISA"), task)
            st.session_state.teacher_pisa_draft = None
            st.success("Тапсырма сыныпқа жіберілді.")
            st.rerun()

    st.subheader("Менің тапсырмаларым")
    saved = DB.teacher_pisa_assignments(user["id"], cls["id"])
    if not saved:
        st.caption("Бұл сыныпқа тапсырма әлі жіберілмеген.")
    for p_row in saved:
        with st.expander(f"{task_display_title(p_row['title'])} · {p_row['topic']} · {p_row['created_at'][:10]}"):
            render_pisa_task(p_row.get("task") or {})
            results = DB.teacher_pisa_results(p_row["id"], user["id"])
            if results:
                st.markdown("#### Оқушылардың жауаптары")
                st.dataframe(pd.DataFrame([{
                    "Оқушы": r["full_name"],
                    "Сұрақ": int(r["question_index"]),
                    "Жауап": r.get("student_answer"),
                    "Дұрыс/үлгі жауап": r.get("correct_answer"),
                    "Нәтиже": "Мұғалім тексереді" if r.get("is_correct") is None else ("Дұрыс" if r.get("is_correct") else "Толықтыру керек"),
                    "Балл": r.get("score"),
                    "Кері байланыс": r.get("feedback"),
                    "Күні": _short_time(r.get("submitted_at")),
                } for r in results]), hide_index=True, use_container_width=True)
                pending = [r for r in results if r.get("is_correct") is None]
                for response in pending:
                    st.markdown(f"**{response['full_name']} · {response['question_index']}-сұрақ:** {response['question_text']}")
                    st.write(f"Оқушы жауабы: {response.get('student_answer') or '—'}")
                    st.caption(f"Үлгі жауап: {response.get('correct_answer') or '—'}")
                    with st.form(f"grade_pisa_{response['id']}"):
                        verdict = st.radio("Мұғалім бағасы", ["Дұрыс", "Толықтыру керек"], key=f"grade_choice_{response['id']}", horizontal=True)
                        note = st.text_input("Түсіндірме", key=f"grade_note_{response['id']}")
                        if st.form_submit_button("Бағаны сақтау"):
                            if DB.grade_pisa_response(response["id"], user["id"], verdict == "Дұрыс", note):
                                st.success("Мұғалім бағасы сақталды.")
                                st.rerun()
            else:
                st.caption("Әзірге жауап жоқ.")
            new_status = "closed" if p_row["status"] == "active" else "active"
            if st.button("Жабу" if new_status == "closed" else "Қайта ашу", key=f"pisa_status_{p_row['id']}"):
                DB.set_pisa_assignment_status(p_row["id"], user["id"], new_status)
                st.rerun()


def _teacher_context_text(user: dict[str, Any], class_id: int | None) -> str:
    if not class_id:
        return ""
    classes = DB.teacher_classes(user["id"])
    cls = next((c for c in classes if int(c["id"]) == int(class_id)), None)
    if not cls:
        return ""
    rows = DB.class_student_overview(class_id)
    summary = [f"Сынып: {cls['name']}. Оқушы саны: {len(rows)}."]
    for r in rows[:40]:
        summary.append(f"- {r['full_name']}: оқу әрекеті {int(r.get('attempt_count') or 0)}, сынып жұмысы {int(r.get('class_work_count') or 0)}, өмірлік тапсырмалар {int(r.get('pisa_work_count') or 0)}")
    return "\n".join(summary)


def page_teacher_assistant(user: dict[str, Any]) -> None:
    page_ai_workspace(user)
    return
    page_header(
        "Мұғалім ЖИ ассистенті",
        "ҚМЖ, БЖБ/ТЖБ, жұмыс парағы, презентация, сурет, тапсырма және сынып талдауын бір чатта дайындаңыз.",
        "МҰҒАЛІМНІҢ ЦИФРЛЫҚ КӨМЕКШІСІ",
    )
    classes = DB.teacher_classes(user["id"])
    opts = [None] + [int(c["id"]) for c in classes]
    context_class = st.selectbox(
        "Сынып контексті (қажет болса)",
        opts,
        format_func=lambda x: "Жалпы сұрақ" if x is None else next(c["name"] for c in classes if int(c["id"]) == int(x)),
        key="teacher_assistant_class",
    )
    upload = st.file_uploader(
        "Файл тіркеу (қажет болса)",
        type=["pdf", "docx", "txt", "md", "csv"],
        key="teacher_assistant_upload",
    )
    st.caption(
        "Мысал: «9-сыныпқа еркін түсу тақырыбынан 45 минуттық ҚМЖ жаса», "
        "«Осы тақырыпқа 7 слайдтық презентация жаса», «Осы тақырыпқа презентацияға арналған мәтінсіз фон жаса»."
    )

    history = DB.assistant_history(user["id"], 60)
    for msg in history:
        with st.chat_message("assistant" if msg["role"] == "assistant" else "user"):
            render_rich_text(msg["content"])

    artifact = st.session_state.get("teacher_assistant_artifact")
    if artifact:
        st.markdown("### Соңғы дайын материал")
        if artifact.get("kind") == "image":
            st.image(artifact["bytes"], caption=artifact["name"], use_container_width=True)
            st.download_button(
                "Суретті жүктеу",
                data=artifact["bytes"],
                file_name=artifact["name"],
                mime=artifact["mime"],
                use_container_width=True,
                type="primary",
            )
        else:
            label = "PPTX файлын жүктеу" if artifact.get("kind") == "pptx" else "Word файлын жүктеу"
            st.download_button(
                label,
                data=artifact["bytes"],
                file_name=artifact["name"],
                mime=artifact["mime"],
                use_container_width=True,
                type="primary",
            )

    retry_prompt = st.session_state.get("teacher_assistant_retry_prompt")
    if retry_prompt:
        st.warning("Соңғы сұрауды орындау аяқталмады. Қайта орындауға болады.")
        if st.button("Соңғы сұрауды қайта орындау", use_container_width=True, key="retry_teacher_assistant"):
            st.session_state.teacher_assistant_pending_prompt = retry_prompt
            st.session_state.teacher_assistant_retry_prompt = None
            st.rerun()

    typed_prompt = st.chat_input("Мұғалім ЖИ ассистентіне тапсырма жазыңыз...")
    pending_prompt = st.session_state.get("teacher_assistant_pending_prompt")
    prompt = pending_prompt or typed_prompt
    is_retry = bool(pending_prompt)

    if prompt:
        if is_retry:
            st.session_state.teacher_assistant_pending_prompt = None
        else:
            DB.add_assistant_message(user["id"], "user", prompt)

        ai = ai_client()
        if not ai.available:
            response = "ЖИ қызметі уақытша қолжетімсіз. Сервер баптауларын тексеріп, кейін қайта көріңіз."
            DB.add_assistant_message(user["id"], "assistant", response)
            st.session_state.teacher_assistant_retry_prompt = prompt
            st.rerun()

        class_context = _teacher_context_text(user, context_class)
        file_context = ""
        if upload is not None:
            try:
                extracted = extract_text(upload.name, upload.getvalue())
                file_context = extracted[:18000]
            except Exception:
                file_context = "Тіркелген файлдан мәтін алу мүмкін болмады."

        # «Осы тақырып», «осыған» сияқты сілтемелерді түсіну үшін соңғы чат контексті беріледі.
        recent_dialogue: list[str] = []
        for msg in history[-12:]:
            who = "Мұғалім" if msg["role"] == "user" else "Ассистент"
            recent_dialogue.append(f"{who}: {str(msg['content'])[:1800]}")
        dialogue_context = "\n".join(recent_dialogue)

        extra_parts: list[str] = []
        if dialogue_context:
            extra_parts.append("Соңғы чат контексті:\n" + dialogue_context)
        if class_context:
            extra_parts.append("Сынып контексті:\n" + class_context)
        if file_context:
            extra_parts.append("Тіркелген файл мәтіні:\n" + file_context)
        extra = "\n\n" + "\n\n".join(extra_parts) if extra_parts else ""

        kind = infer_artifact_kind(prompt)
        try:
            if kind == "pptx":
                data = ai.json(
                    "Сен Қазақстан мектебінің тәжірибелі әдіскері және презентация құрастырушысысың. "
                    "Соңғы чат контекстін ескер. Мұғалім сұрағына сай мазмұнды, нақты және мектепте бірден қолданылатын презентация құр. "
                    "Слайдтарда артық мәтін болмауы тиіс. Жауапты тек JSON бер.",
                    prompt + extra + '\nJSON: {"title":"...","slides":[{"title":"...","bullets":["...","..."]}]}. '
                    "Слайд санын мұғалім айтса дәл сақта, айтпаса 7 слайд жаса.",
                )
                slides = data.get("slides") if isinstance(data, dict) else []
                if not isinstance(slides, list) or not slides:
                    raise RuntimeError("presentation_generation_failed")
                title_text = str(data.get("title") or "Презентация")
                blob = build_pptx_bytes(title_text, slides)
                name = "teacher_presentation.pptx"
                st.session_state.teacher_assistant_artifact = {
                    "kind": "pptx",
                    "bytes": blob,
                    "name": name,
                    "mime": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                }
                response = f"«{title_text}» презентациясы дайын. PPTX файлын төмендегі батырма арқылы жүктей аласыз."
                DB.add_assistant_message(user["id"], "assistant", response, "pptx", name)

            elif kind == "docx":
                content = ai.text(
                    "Сен Қазақстан мектебінің тәжірибелі мұғалімі және әдіскері бол. Соңғы чат контекстін ескер. "
                    "Пайдаланушы сұраған материалды қазақ тілінде, мектепте бірден қолдануға болатын толық нұсқада дайында. "
                    "Егер ҚМЖ болса оқу мақсаты, сабақ мақсаты, кезеңдер, мұғалім/оқушы әрекеті, бағалау және ресурстарды қамты. "
                    "Егер БЖБ/ТЖБ болса тапсырмалар, балл және бағалау критерийін қамты.",
                    prompt + extra,
                )
                title_text = prompt.strip()[:90]
                blob = build_docx_bytes(title_text, content)
                name = "teacher_material.docx"
                st.session_state.teacher_assistant_artifact = {
                    "kind": "docx",
                    "bytes": blob,
                    "name": name,
                    "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                }
                response = content + "\n\nWord файлы дайын."
                DB.add_assistant_message(user["id"], "assistant", response, "docx", name)

            elif kind == "image":
                low_prompt = prompt.lower()
                is_background = "фон" in low_prompt or "background" in low_prompt
                image_system = (
                    "Мұғалім сұраған презентация фоны үшін сурет генераторына бір нақты prompt жаз. "
                    "Соңғы чат контекстінен тақырыпты анықта. Кең 16:9 композиция болсын, мәтін, әріп, логотип, сутаңба, интерфейс элементтері болмасын; "
                    "негізгі мазмұн слайд мәтінін орналастыруға кедергі жасамайтындай шеттерге жұмсақ таралсын. Тек prompt қайтар."
                    if is_background else
                    "Мұғалім сұраған білім беру суреті үшін сурет генераторына бір нақты, қауіпсіз, тақырыпқа дәл сәйкес prompt жаз. "
                    "Соңғы чат контекстін ескер. Суреттің ішіне ұзын мәтін, логотип немесе интерфейс элементтерін салма. Тек prompt қайтар."
                )
                image_prompt = ai.text(image_system, prompt + extra)
                blob = ai.image(image_prompt, size="1536x1024")
                name = "presentation_background.png" if is_background else "teacher_visual.png"
                st.session_state.teacher_assistant_artifact = {
                    "kind": "image",
                    "bytes": blob,
                    "name": name,
                    "mime": "image/png",
                }
                response = "Тақырыпқа сай презентациялық фон дайын." if is_background else "Сұраған көрнекі сурет дайын."
                DB.add_assistant_message(user["id"], "assistant", response, "image", name)

            else:
                response = ai.text(
                    "Сен мұғалімнің әмбебап ЖИ ассистентісің. Соңғы чат контекстін ескер. "
                    "Қазақстан мектебінің оқу үдерісіне сай нақты, пайдалы және бірден қолдануға болатын жауап бер. "
                    "Қажет болса кесте, тапсырма, жоспар, талдау немесе бағалау критерийін мәтін түрінде дайында. "
                    "Формулаларды стандартты LaTeX түрінде жаз.",
                    prompt + extra,
                )
                st.session_state.teacher_assistant_artifact = None
                DB.add_assistant_message(user["id"], "assistant", response)

            st.session_state.teacher_assistant_retry_prompt = None
        except Exception:
            st.session_state.teacher_assistant_retry_prompt = prompt
            DB.add_assistant_message(
                user["id"],
                "assistant",
                "Сұрауды орындау уақытша аяқталмады. «Соңғы сұрауды қайта орындау» батырмасы арқылы қайталап көріңіз.",
            )
        st.rerun()

    if st.button("Чат тарихын тазарту", key="clear_teacher_assistant"):
        DB.clear_assistant_history(user["id"])
        st.session_state.teacher_assistant_artifact = None
        st.session_state.teacher_assistant_retry_prompt = None
        st.session_state.teacher_assistant_pending_prompt = None
        st.rerun()


def page_generator(user: dict[str, Any]) -> None:
    st.title("🧩 Тапсырма генераторы")
    grade = st.selectbox("Сынып", SUPPORTED_GRADES, index=2)
    topic = st.text_input("Тақырып", placeholder="Тақырыпты енгізіңіз...")
    level = st.selectbox("Деңгей", ["A","B","C"])
    goal = st.text_input("Оқу мақсаты / нақты талап", placeholder="Қажет болса нақты талапты жазыңыз...")
    if st.button("Тапсырма құру", use_container_width=True, type="primary"):
        if not topic.strip():
            st.error("Тақырыпты енгізіңіз.")
            return
        task = generate_task(ai_client(), grade, topic.strip(), level, goal)
        if task:
            st.session_state["teacher_generated_task"] = task
        else:
            st.error("Тапсырманы құру мүмкін болмады. Кейінірек қайталап көріңіз.")
    task = st.session_state.get("teacher_generated_task")
    if task:
        st.markdown("### Дайын тапсырма")
        st.markdown(f"**Тақырып:** {escape(str(task.get('topic') or topic))} · **Деңгей:** {escape(str(task.get('difficulty') or level))}")
        st.markdown(f"**Тапсырма:** {normalize_math(str(task.get('question') or ''))}")
        if task.get("options"):
            for opt in task["options"]:
                st.write(f"• {opt}")
        with st.expander("Жауабы мен шешуін көру"):
            st.write(f"Дұрыс жауап: {task.get('answer') or '—'}")
            st.markdown("**Шешуі:**")
            render_rich_text(str(task.get("solution") or "—"))


def run() -> None:
    init_state()
    if not st.session_state.user:
        auth_screen()
        return
    user = refresh_user()
    page = sidebar()
    if user["role"] == "student":
        if page == "Басты бет": page_student_home(user)
        elif page == "Диагностика": page_diagnostic(user)
        elif page == "Адаптивті оқу": page_adaptive(user)
        elif page == "Тапсырмалар": page_student_assignments(user)
        elif page == "Функционалдық сауаттылық және PISA": page_pisa(user)
        elif page == "Қатемен жұмыс": page_errors(user)
        elif page == "ЖИ мұғалім": page_tutor(user)
        elif page == "Прогресс": page_progress(user)
        elif page == "Профиль": page_profile(user)
        elif page == "Баптаулар": page_settings()
    else:
        if page == "Мұғалім панелі": page_teacher_dashboard(user)
        elif page == "Сыныптар": page_classes(user)
        elif page == "Оқушылар": page_teacher_students(user)
        elif page == "Сынып тапсырмалары": page_teacher_assignments(user)
        elif page == "Функционалдық сауаттылық және PISA": page_teacher_pisa(user)
        elif page == "Мұғалім ЖИ ассистенті": page_teacher_assistant(user)
        elif page == "Материалдар": page_materials(user)
        elif page == "Тапсырма генераторы": page_generator(user)
        elif page == "Баптаулар": page_settings()


if __name__ == "__main__":
    run()
