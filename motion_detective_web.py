"""Web version of the grade-seven uniform-motion desktop experiment.

This module is imported lazily by app.py. It needs no PyQt6 and does not write to
other students' records or expose teacher answers to student sessions.
"""
from __future__ import annotations

import re
import time
from html import escape

import plotly.graph_objects as go
import streamlit as st

MOVERS = (
    ("Жаяу жүргінші", 1.5, "#2474cb"),
    ("Велосипедші", 5.0, "#eb8d25"),
    ("Самокатшы", 10.0, "#279366"),
)
MAX_TIME = 40


def distance(speed: float, seconds: float) -> float:
    if speed < 0 or seconds < 0:
        raise ValueError("Жылдамдық пен уақыт теріс болмауы тиіс")
    return speed * seconds


def speed_from_distance(path: float, seconds: float) -> float:
    if path < 0 or seconds <= 0:
        raise ValueError("Жол теріс емес, уақыт нөлден үлкен болуы тиіс")
    return path / seconds


def convert_speed(value: float, to_kmh: bool) -> float:
    if value < 0:
        raise ValueError("Жылдамдық теріс болмауы тиіс")
    return value * 3.6 if to_kmh else value / 3.6


def near(value: float, expected: float) -> bool:
    return abs(value - expected) <= 0.05


def experiment_rows(bike_speed: float, reference: int, target: int, revealed: bool) -> list[dict]:
    times = sorted(set(list(range(0, MAX_TIME + 1, 10)) + [reference, target])) if revealed else sorted(set([0, min(10, reference), reference]))
    return [{"Уақыт, с": t,
             "Жаяу жүргінші, м": distance(MOVERS[0][1], t),
             "Велосипедші, м": distance(bike_speed, t),
             "Самокатшы, м": distance(MOVERS[2][1], t)} for t in times]


def _init_state(user: dict) -> None:
    owner = user.get("id")
    if st.session_state.get("motion_owner") != owner:
        for key in tuple(st.session_state.keys()):
            if key.startswith("motion_"):
                del st.session_state[key]
        st.session_state.motion_owner = owner
    defaults = {
        "motion_speed": 5.0, "motion_ref": 20, "motion_target": 30,
        "motion_time": 0.0, "motion_playing": False,
        "motion_last_tick": time.monotonic(), "motion_prediction": None,
        "motion_revealed": False, "motion_speed_feedback": "",
        "motion_convert_feedback": "", "motion_conclusion_feedback": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _reset_prediction() -> None:
    state = st.session_state
    state.motion_ref = int(state.motion_ref)
    if state.motion_target <= state.motion_ref:
        state.motion_target = state.motion_ref + 1
    state.motion_time = 0.0
    state.motion_playing = False
    state.motion_prediction = None
    state.motion_revealed = False
    state.motion_conclusion_feedback = ""


def _track_html(seconds: float, bike_speed: float) -> str:
    movers = (MOVERS[0], (MOVERS[1][0], bike_speed, MOVERS[1][2]), MOVERS[2])
    maximum = max(400.0, max(speed for _, speed, _ in movers) * MAX_TIME)
    rows = []
    for name, speed, color in movers:
        travelled = distance(speed, seconds)
        pct = min(100.0, 100.0 * travelled / maximum)
        rows.append(
            f'<div class="md-row"><span class="md-name">{escape(name)}</span>'
            '<div class="md-lane">'
            f'<span class="md-marker" style="left:{pct:.3f}%;background:{color}"></span>'
            f'<span class="md-meters" style="left:{min(pct, 91):.3f}%;color:{color}">{travelled:g} м</span>'
            '</div></div>'
        )
    return ("<style>"
            ".md-scene{background:#f8fbff;border:1px solid #dfe8f4;border-radius:14px;"
            "padding:15px 22px;margin:8px 0 14px;font:16px 'Times New Roman',serif}"
            ".md-row{display:grid;grid-template-columns:155px minmax(0,1fr);gap:18px;"
            "align-items:center;height:67px}.md-name{font-weight:700;color:#17324f}"
            ".md-lane{position:relative;height:2px;background:#cedded;margin-right:42px}"
            ".md-marker{position:absolute;width:19px;height:19px;border-radius:50%;"
            "top:-9px;transform:translateX(-50%)}.md-meters{position:absolute;"
            "font-weight:700;white-space:nowrap;top:-30px;transform:translateX(-5%)}"
            "@media(max-width:650px){.md-row{grid-template-columns:110px minmax(0,1fr);gap:8px}"
            ".md-scene{padding:12px 8px}.md-name{font-size:13px}}"
            "</style><div class='md-scene'>" + "".join(rows) + "</div>")


def _graph(name: str, speed: float, color: str, seconds: float, end: int) -> go.Figure:
    xs = list(range(end + 1))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=[distance(speed, t) for t in xs],
                             mode="lines", name=name, line={"color": color, "width": 3}))
    marker_time = min(seconds, end)
    fig.add_trace(go.Scatter(x=[marker_time], y=[distance(speed, marker_time)],
                             mode="markers", marker={"size": 12, "color": color},
                             showlegend=False, hovertemplate="%{x:.1f} с · %{y:.1f} м<extra></extra>"))
    fig.update_layout(height=330, margin={"l": 35, "r": 12, "t": 12, "b": 35},
                      xaxis={"title": "Уақыт, с", "range": [0, MAX_TIME], "dtick": 10},
                      yaxis={"title": "Жол, м", "range": [0, distance(speed, MAX_TIME) * 1.12]},
                      showlegend=False, paper_bgcolor="white", plot_bgcolor="white")
    return fig


@st.fragment(run_every="0.3s")
def _motion_stage() -> None:
    s = st.session_state
    limit = MAX_TIME if s.motion_revealed else int(s.motion_ref)
    if s.motion_playing:
        now = time.monotonic()
        s.motion_time = min(float(limit), round(float(s.motion_time) + min(now - s.motion_last_tick, 0.8), 1))
        s.motion_last_tick = now
        if s.motion_time >= limit:
            s.motion_playing = False
    st.markdown("#### Үш нысанның қозғалысы")
    st.caption("Басқарылатын шама — уақыт; тұрақты шамалар — нысандардың жылдамдығы; бақыланатын шама — жүрген жол.")
    st.html(_track_html(float(s.motion_time), float(s.motion_speed)))
    first, second, third = st.columns([1, 1, 4])
    with first:
        if st.button("⏸ Тоқтату" if s.motion_playing else "▶ Ойнату", key="motion_play_button", width="stretch"):
            if s.motion_time >= limit:
                s.motion_time = 0.0
            s.motion_playing = not s.motion_playing
            s.motion_last_tick = time.monotonic()
            st.rerun(scope="fragment")
    with second:
        if st.button("↺ Басына", key="motion_reset_button", width="stretch"):
            s.motion_time = 0.0
            s.motion_playing = False
            st.rerun(scope="fragment")
    with third:
        st.slider("Уақыт, с", 0.0, float(limit), step=0.1, key="motion_time")
    if not s.motion_revealed:
        st.info(f"{s.motion_target} секундтағы деректер болжам тексерілгеннен кейін ашылады.")
    st.markdown("#### Әр нысанның жеке жол–уақыт графигі")
    graph_tabs = st.tabs([item[0] for item in MOVERS])
    for tab, (name, default_speed, color) in zip(graph_tabs, MOVERS):
        with tab:
            actual_speed = float(s.motion_speed) if name == "Велосипедші" else default_speed
            st.plotly_chart(_graph(name, actual_speed, color, float(s.motion_time), limit),
                            width="stretch", config={"displayModeBar": False},
                            key=f"motion_graph_{name}")
    st.caption("Көлденең ось — уақыт (с), тік ось — жол (м). Сызық неғұрлым тік болса, нысан соғұрлым жылдам қозғалады.")
    st.markdown("#### Кесте: s = v × t")
    st.dataframe(experiment_rows(float(s.motion_speed), int(s.motion_ref),
                                 int(s.motion_target), bool(s.motion_revealed)),
                 hide_index=True, width="stretch")


def _tasks() -> None:
    s = st.session_state
    st.subheader("Өз мәндеріңізбен есептеңіз")
    st.markdown("##### 1. Жылдамдықты табу")
    with st.form("motion_speed_form"):
        col1, col2, col3 = st.columns(3)
        path = col1.number_input("Жол, м", min_value=0.0, max_value=100000.0,
                                 value=100.0, step=1.0, key="motion_path")
        seconds = col2.number_input("Уақыт, с", min_value=0.1, max_value=10000.0,
                                    value=20.0, step=0.1, key="motion_duration")
        answer = col3.number_input("Сіздің жауабыңыз, м/с", min_value=0.0,
                                   max_value=100000.0, step=0.1, key="motion_speed_answer")
        submitted = st.form_submit_button("Жылдамдықты тексеру")
    if submitted:
        expected = speed_from_distance(float(path), float(seconds))
        s.motion_speed_feedback = (f"Дұрыс! {path:g} м / {seconds:g} с = {expected:g} м/с."
                                   if near(float(answer), expected) else
                                   f"Жолды уақытқа бөліңіз: {path:g} м / {seconds:g} с = ?")
    if s.motion_speed_feedback:
        st.success(s.motion_speed_feedback) if s.motion_speed_feedback.startswith("Дұрыс") else st.warning(s.motion_speed_feedback)

    st.markdown("##### 2. Өлшем бірлігін түрлендіру")
    with st.form("motion_conversion_form"):
        direction = st.selectbox("Бағыты", ["м/с → км/сағ", "км/сағ → м/с"], key="motion_direction")
        c1, c2 = st.columns(2)
        start_value = c1.number_input("Берілген мән", min_value=0.0, max_value=100000.0,
                                      value=5.0, key="motion_convert_value")
        converted_answer = c2.number_input("Сіздің жауабыңыз", min_value=0.0,
                                            max_value=1000000.0, key="motion_convert_answer")
        submitted_convert = st.form_submit_button("Түрлендіруді тексеру")
    if submitted_convert:
        to_kmh = direction.startswith("м/с")
        expected = convert_speed(float(start_value), to_kmh)
        s.motion_convert_feedback = ("Дұрыс! Түрлендіру орындалды." if near(float(converted_answer), expected)
                                     else ("3,6-ға көбейтіңіз." if to_kmh else "3,6-ға бөліңіз."))
    if s.motion_convert_feedback:
        st.success(s.motion_convert_feedback) if s.motion_convert_feedback.startswith("Дұрыс") else st.warning(s.motion_convert_feedback)

    st.markdown("##### 3. Болжау → тексеру → қорытынды")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.number_input("Велосипедшінің жылдамдығы, м/с", 0.1, 30.0, step=0.1,
                        key="motion_speed", on_change=_reset_prediction)
    with c2:
        st.number_input("Бастапқы уақыт, с", 1, 38, step=1,
                        key="motion_ref", on_change=_reset_prediction)
    with c3:
        st.number_input("Болжайтын уақыт, с", int(s.motion_ref) + 1, MAX_TIME,
                        step=1, key="motion_target", on_change=_reset_prediction)
    reference = int(s.motion_ref)
    target = int(s.motion_target)
    speed = float(s.motion_speed)
    st.write(f"Велосипедші {reference} с-та **{distance(speed, reference):g} м** жүрді. "
             f"Жылдамдығы {speed:g} м/с болып қалса, {target} с-та қанша метр жүреді?")
    prediction = st.number_input("Алдымен жолды болжаңыз, м", min_value=0.0,
                                  max_value=100000.0, step=1.0, key="motion_prediction_input")
    col_save, col_check = st.columns(2)
    with col_save:
        if st.button("Болжамды тіркеу", key="motion_save_prediction", width="stretch"):
            s.motion_prediction = float(prediction)
            s.motion_revealed = False
            s.motion_playing = False
            s.motion_time = 0.0
            st.rerun()
    with col_check:
        if st.button("Болжамды тексеру", key="motion_verify_prediction", width="stretch",
                     disabled=s.motion_prediction is None):
            s.motion_revealed = True
            s.motion_playing = False
            s.motion_time = float(target)
            st.rerun()
    if s.motion_prediction is not None and not s.motion_revealed:
        st.caption(f"Болжам тіркелді: {s.motion_prediction:g} м. Тексеру үшін батырманы басыңыз.")
    if s.motion_revealed:
        expected = distance(speed, target)
        st.write(f"**Тексеру:** s = v × t = {speed:g} м/с × {target} с = **{expected:g} м**.")
        if near(float(s.motion_prediction), expected):
            st.success("Болжам модельдік нәтижемен сәйкес келді.")
        else:
            st.warning("Болжам мен нәтиже әртүрлі. Формуланы қайта қолданып, жаңа болжам жасаңыз.")
        text = st.text_area("Қорытындыңыз: уақыт өзгергенде жол қалай өзгерді? Жылдамдық не болды?",
                            key="motion_conclusion")
        if st.button("Қорытынды бойынша кеңес алу", key="motion_conclusion_check"):
            numbers = [float(x.replace(",", ".")) for x in re.findall(r"(?<!\d)\d+(?:[.,]\d+)?(?!\d)", text)]
            expected_start = distance(speed, reference)
            if not text.strip():
                s.motion_conclusion_feedback = "Алдымен өз қорытындыңызды жазыңыз."
            elif not (any(near(x, reference) for x in numbers) and any(near(x, target) for x in numbers)
                      and any(near(x, expected_start) for x in numbers) and any(near(x, expected) for x in numbers)):
                s.motion_conclusion_feedback = "Екі уақытты және олардың әрқайсысындағы жүрген жолды салыстырыңыз."
            else:
                s.motion_conclusion_feedback = "Негізгі сандар келтірілді. Түсіндірменің мағынасын мұғаліммен талқылаңыз."
        if s.motion_conclusion_feedback:
            st.info(s.motion_conclusion_feedback)


def _teacher_view() -> None:
    s = st.session_state
    speed, reference, target = float(s.motion_speed), int(s.motion_ref), int(s.motion_target)
    st.subheader("Мұғалімге: есептеулер мен қателер")
    st.caption("Жауаптар тек мұғалім аккаунтына көрсетіледі. Еркін қорытындыны мұғалім өзі бағалайды.")
    path, duration = float(s.get("motion_path", 100.0)), float(s.get("motion_duration", 20.0))
    amount = float(s.get("motion_convert_value", 5.0))
    to_kmh = s.get("motion_direction", "м/с → км/сағ").startswith("м/с")
    st.write(f"1-есеп: {path:g} м / {duration:g} с = **{speed_from_distance(path, duration):g} м/с**.")
    st.write(f"2-есеп: {amount:g} → **{convert_speed(amount, to_kmh):g}** "
             f"{'км/сағ' if to_kmh else 'м/с'}. Осы бағытта 3,6-ға "
             f"{'көбейтіледі' if to_kmh else 'бөлінеді'}.")
    st.write(f"3-есеп: {reference} с-та **{distance(speed, reference):g} м**, "
             f"{target} с-та **{distance(speed, target):g} м**. "
             f"Жол айырмасы **{distance(speed, target-reference):g} м**; жылдамдық тұрақты.")
    st.table([
        {"Ықтимал қате": "v = t / s", "Түсіндірме": "Жылдамдық жолды уақытқа бөлгенде табылады: v = s / t (м/с)."},
        {"Ықтимал қате": "s = v / t", "Түсіндірме": "Жолды табу үшін жылдамдық пен уақытты көбейтеміз: s = v × t."},
        {"Ықтимал қате": "м/с → км/сағ-та 3,6-ға бөлу", "Түсіндірме": "Осы бағытта 3,6-ға көбейтеміз; кері бағытта бөлеміз."},
        {"Ықтимал қате": "Ескі жолды жаңа уақытқа көшіру", "Түсіндірме": "Жаңа уақытты s = v × t формуласына қойып, жолды қайта есептейміз."},
        {"Ықтимал қате": "График осьтерін шатастыру", "Түсіндірме": "Көлденеңі уақыт (с), тігі жол (м); көлбеуі жылдамдықты көрсетеді."},
    ])


def render_motion_detective(user: dict) -> None:
    """Use the existing site authentication and role data."""
    _init_state(user)
    st.title("🔎 Қозғалыс детективі: кім жылдамырақ?")
    st.caption("7-сынып · Бірқалыпты қозғалыс · Үш нысанның модельдік қозғалысы")
    st.info("Жылдамдықтар тәжірибеде өлшенген емес, оқу үшін алынған модельдік деректер.")
    if user.get("role") == "teacher":
        tab_lab, tab_tasks, tab_teacher = st.tabs(["Қозғалыс моделі", "Оқушы тапсырмалары", "Мұғалімге"])
    else:
        tab_lab, tab_tasks = st.tabs(["Қозғалыс моделі", "Оқушы тапсырмалары"])
    with tab_tasks:
        _tasks()
    with tab_lab:
        _motion_stage()
    if user.get("role") == "teacher":
        with tab_teacher:
            _teacher_view()
