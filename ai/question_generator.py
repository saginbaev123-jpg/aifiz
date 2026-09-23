from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from ai.openai_client import AIClient
from ai.assessment import NUMBER
from ai.pisa_agent import choose_pisa_visual
from ai_core.visual_engine import infer_diagram_type, validate_diagram_spec, DIAGRAM_TYPES

logger = logging.getLogger(__name__)


def clean_descriptors(value: Any) -> list[dict[str, Any]]:
    """Keep only concrete, positive-point scoring steps returned by the model."""
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for row in value[:8]:
        if not isinstance(row, dict):
            continue
        description = str(row.get("description") or "").strip()
        try:
            points = int(row.get("points"))
        except (TypeError, ValueError):
            continue
        if description and 1 <= points <= 10:
            result.append({"description": description, "points": points})
    return result


def generate_descriptors(ai: AIClient, grade: int, question: str, answer: str, solution: str, goal: str = "") -> list[dict[str, Any]]:
    """Propose a point rubric for a teacher-written task; never invent one offline."""
    if not ai.available or not question.strip():
        return []
    try:
        data = ai.json(
            "Сен физика мұғалімісің. Бір нақты тапсырмаға тексерілетін, бірін-бірі қайталамайтын дескрипторлар мен бүтін баллдар құр. Тек JSON объект бер.",
            f"Сынып: {grade}\nСұрақ: {question}\nДұрыс жауап: {answer}\nШешуі: {solution}\nОқу мақсаты: {goal}\n"
            'JSON: {"descriptors":[{"description":"Оқушы орындайтын нақты қадам", "points":1}]}. '
            "Формула, есептеу, жауап пен өлшем бірлігін тапсырмаға сәйкес бөлек бағала; қажет емес талап қоспа.",
        )
    except Exception:
        logger.exception("Descriptor generation failed")
        return []
    return clean_descriptors(data.get("descriptors")) if isinstance(data, dict) else []


def _clean_task(data: dict[str, Any], grade: int, topic: str, level: str) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    q = str(data.get("question", "")).strip()
    answer = str(data.get("answer", "")).strip()
    solution = str(data.get("solution", "")).strip()
    qtype = str(data.get("type", "numeric")).strip().lower()
    if qtype not in {"numeric", "mcq"}:
        qtype = "numeric"
    options = data.get("options") or []
    if not isinstance(options, list):
        options = []
    options = [str(x).strip() for x in options if str(x).strip()]
    if not q or not answer or not solution:
        return None
    if qtype == "mcq":
        if len(options) != 4 or len(set(options)) != 4 or answer not in options:
            return None
    elif not NUMBER.fullmatch(answer):
        return None
    return {
        "id": str(data.get("id") or f"AI-{uuid.uuid4().hex[:10].upper()}"),
        "grade": grade,
        "topic": topic,
        "difficulty": level,
        "type": qtype,
        "question": q,
        "options": options,
        "answer": answer,
        "solution": solution,
        "descriptors": clean_descriptors(data.get("descriptors")),
        "descriptor_basis": [q, answer, solution],
        "error_hint": str(data.get("error_hint") or "CONCEPT_ERROR").strip(),
        "source": "openai",
    }


def generate_task(
    ai: AIClient,
    grade: int,
    topic: str,
    level: str,
    learning_goal: str = "",
    *,
    mastery: float | None = None,
    mistake_context: str = "",
    avoid_questions: list[str] | None = None,
) -> dict[str, Any] | None:
    """Generate one unique adaptive physics task through the API.

    Local task banks are intentionally not used here. Callers may choose an
    offline fallback only when the API is unavailable.
    """
    if not ai.available:
        return None
    avoid_questions = (avoid_questions or [])[-8:]
    avoid_text = "\n".join(f"- {q[:240]}" for q in avoid_questions) or "- жоқ"
    mastery_text = f"{mastery:.0f}%" if mastery is not None else "белгісіз"
    try:
        data = ai.json(
            """Сен Қазақстан мектебінің тәжірибелі физика мұғалімісің және адаптивті тапсырма генераторысың.
Физикалық есептің шарты жеткілікті, жауабы бірмәнді және шешімі есептеумен тексерілген болсын.
Оқушы деңгейіне сай болсын. Бұрынғы сұрақты сөзбе-сөз немесе тек сандарын ауыстырып қайталама.
Қате түрін тек мына кодтардың біреуімен белгіле: FORMULA_ERROR, SI_ERROR, CALCULATION_ERROR,
CONCEPT_ERROR, VECTOR_ERROR, GRAPH_ERROR, UNIT_ERROR, READING_ERROR.
Жауапты тек JSON объект ретінде бер.""",
            f"""Сынып: {grade}
Тақырып: {topic}
Деңгей: {level} (A — базалық, B — қолдану, C — күрделі/талдау)
Меңгеру көрсеткіші: {mastery_text}
Оқу мақсаты: {learning_goal or 'тақырыпты меңгеру және білімді қолдану'}
Оқушының қате контексті: {mistake_context or 'арнайы қате контексті жоқ'}

Қайталамау керек соңғы сұрақтар:
{avoid_text}

Бір ғана жаңа тапсырма құрастыр. numeric немесе mcq түрін таңда. Егер mcq болса дәл 4 нұсқа бер және answer options ішіндегі нұсқамен дәлме-дәл бірдей болсын.
JSON форматы:
{{"id":"AI-...","question":"...","type":"numeric|mcq","options":["..."],"answer":"...","solution":"қадамдық қысқа шешім","error_hint":"FORMULA_ERROR"}}""",
        )
        return _clean_task(data, grade, topic, level)
    except Exception:
        return None


def generate_assignment_tasks(
    ai: AIClient, grade: int, topic: str, level: str, count: int, learning_goal: str = ""
) -> list[dict[str, Any]]:
    """Create classroom questions in small batches, keeping only complete unique tasks."""
    if not ai.available:
        return []
    tasks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _ in range(3):
        if len(tasks) >= count:
            break
        remaining = count - len(tasks)
        for start in range(0, remaining, 6):
            needed = min(6, remaining - start)
            try:
                data = ai.json(
                    "Сен физика мұғалімісің. Дәл сұралған санға сай, бір-бірінен бөлек, жауабы мен шешімі дұрыс есептер шығар. Тек JSON объект бер.",
                    f"Сынып: {grade}\nТақырып: {topic}\nДеңгей: {level}\nОқу мақсаты: {learning_goal}\n"
                    f"Дәл {needed} жаңа сұрақ. Бұрынғы сұрақтарды қайталама: "
                    f"{json.dumps([t['question'] for t in tasks][-30:], ensure_ascii=False)}\n"
                    'JSON: {"questions":[{"question":"...","type":"numeric|mcq",'
                    '"options":[],"answer":"...","solution":"...","descriptors":[{"description":"Нақты тексерілетін қадам","points":1}],"error_hint":"CONCEPT_ERROR"}]}. '
                    "numeric жауап таза сан болсын; mcq жауабы төрт нұсқаның бірі болсын.",
                )
            except Exception:
                logger.exception("Classroom question batch generation failed")
                return tasks
            raw = data.get("questions") if isinstance(data, dict) else None
            if not isinstance(raw, list):
                continue
            for row in raw[:needed]:
                task = _clean_task(row, grade, topic, level)
                if task:
                    normalized = re.sub(r"\s+", " ", task["question"]).casefold()
                    if normalized not in seen:
                        seen.add(normalized)
                        tasks.append(task)
    return tasks[:count]


def generate_diagnostic(
    ai: AIClient,
    grade: int,
    topics: list[str],
    count: int = 12,
    *,
    avoid_questions: list[str] | None = None,
) -> list[dict[str, Any]] | None:
    """Generate a balanced diagnostic test as one API request."""
    if not ai.available or not topics:
        return None
    count = max(6, min(18, int(count)))
    avoid_questions = (avoid_questions or [])[-12:]
    avoid_normalized = {re.sub(r"\s+", " ", str(q)).strip().casefold() for q in avoid_questions}
    try:
        data = ai.json(
            """Сен Қазақстан мектебіндегі физика пәнінен диагностикалық бағалау құрастырушы әдіскерсің.
Тест тақырыптарды теңгерімді қамтуы, A/B/C күрделілік деңгейлері аралас болуы және әр сұрақтың нақты жауабы мен қысқа шешімі болуы тиіс.
Физикалық немесе математикалық қатесі бар тапсырма шығарма. Бір сұрақ екіншісінің жауабын ашпасын.
Жауапты тек JSON объект ретінде бер.""",
            f"""Сынып: {grade}
Тақырыптар: {json.dumps(topics, ensure_ascii=False)}
Сұрақ саны: {count}
Ұсынылатын үлес: A ≈ 35%, B ≈ 45%, C ≈ 20%.
Түрлері: numeric және mcq аралас. mcq болса дәл 4 жауап нұсқасы болсын.

Қайталамау керек бұрынғы сұрақтар:
{json.dumps(avoid_questions, ensure_ascii=False)}

JSON:
{{"questions":[{{"id":"DIAG-AI-1","topic":"тақырып атауы тізімнен дәл алынсын","difficulty":"A|B|C","type":"numeric|mcq","question":"...","options":["..."],"answer":"...","solution":"...","error_hint":"CONCEPT_ERROR"}}]}}""",
        )
        raw = data.get("questions") if isinstance(data, dict) else None
        if not isinstance(raw, list):
            return None
        cleaned: list[dict[str, Any]] = []
        seen_normalized: set[str] = set()
        allowed_topics = set(topics)
        for item in raw:
            if not isinstance(item, dict):
                continue
            topic = str(item.get("topic", "")).strip()
            if topic not in allowed_topics:
                topic = topics[len(cleaned) % len(topics)]
            level = str(item.get("difficulty", "B")).upper()
            if level not in {"A", "B", "C"}:
                level = "B"
            task = _clean_task(item, grade, topic, level)
            if task:
                normalized = re.sub(r"\s+", " ", task["question"]).strip().casefold()
                if normalized in seen_normalized or normalized in avoid_normalized:
                    continue
                seen_normalized.add(normalized)
                task["id"] = str(item.get("id") or f"DIAG-AI-{len(cleaned)+1}")
                cleaned.append(task)
            if len(cleaned) >= count:
                break
        return cleaned if len(cleaned) >= max(6, count // 2) else None
    except Exception:
        return None




_TOPIC_STOPWORDS = {"және", "мен", "пен", "бен", "туралы", "арқылы", "кезіндегі", "кезінде", "бойынша", "үшін", "оның", "олардың", "физика", "тақырып"}


def _topic_roots(topic: str) -> list[str]:
    words = re.findall(r"[A-Za-zА-Яа-яӘәҒғҚқҢңӨөҰұҮүҺһІіЁё]{4,}", str(topic or "").casefold())
    roots: list[str] = []
    for word in words:
        if word in _TOPIC_STOPWORDS:
            continue
        root = word[:6] if len(word) >= 7 else word[:5] if len(word) >= 6 else word
        if root not in roots:
            roots.append(root)
    return roots


def _scenario_matches_topic(topic: str, candidate: dict[str, Any]) -> bool:
    roots = _topic_roots(topic)
    if not roots:
        return True
    questions = candidate.get("questions") if isinstance(candidate.get("questions"), list) else []
    qtext = " ".join(str(q.get("q") or "") for q in questions if isinstance(q, dict))
    body = " ".join([str(candidate.get("title") or ""), str(candidate.get("scenario") or ""), qtext]).casefold()
    if any(root in body for root in roots):
        return True
    # Broad chapter names need semantic synonyms; e.g. a motion scenario may
    # correctly cover "кинематика" without repeating that exact word.
    topic_low = str(topic).casefold()
    if "кинемат" in topic_low:
        return any(word in body for word in ("қозғал", "жылдам", "үдеу", "уақыт", "қашық", "орын ауыст"))
    return False


def _scenario_semantically_matches_topic(ai: AIClient, topic: str, candidate: dict[str, Any]) -> bool:
    """Check topic relevance when the scenario uses a different wording."""
    questions = candidate.get("questions") if isinstance(candidate.get("questions"), list) else []
    qtext = "\n".join(str(q.get("q") or "") for q in questions if isinstance(q, dict))
    try:
        verdict = ai.json(
            "Сен физика тапсырмасының тақырыпқа сәйкестігін тәуелсіз тексересің. "
            "Тақырып сөзін жай қайталау жеткіліксіз: жағдаят пен сұрақтар осы физикалық ұғымды "
            "шынымен қолдануы керек. Басқа тараудағы тапсырманы қабылдама. "
            'Тек JSON қайтар: {"relevant": true немесе false}.',
            f"Таңдалған тақырып: {topic}\n"
            f"Жағдаят: {candidate.get('scenario') or ''}\n"
            f"Сұрақтар:\n{qtext}\n"
            'JSON: {"relevant": true немесе false}',
        )
    except Exception:
        logger.warning("PISA semantic topic check failed", exc_info=True)
        return False
    return isinstance(verdict, dict) and verdict.get("relevant") is True


def _clean_pisa_question(q: Any) -> dict[str, Any] | None:
    if not isinstance(q, dict) or not str(q.get("q") or q.get("question") or "").strip():
        return None
    qtype = str(q.get("type", "open")).lower()
    if qtype not in {"numeric", "open"}:
        qtype = "open"
    item: dict[str, Any] = {
        "q": str(q.get("q") or q.get("question") or "").strip(),
        "type": qtype,
        "rubric": str(q.get("rubric", "")).strip(),
        "sample_answer": str(q.get("sample_answer", "")).strip(),
    }
    if qtype == "numeric":
        item["answer"] = str(q.get("answer", "")).strip()
        try:
            item["tolerance"] = float(q.get("tolerance", 0.02) or 0.02)
        except (TypeError, ValueError):
            item["tolerance"] = 0.02
        if not item["answer"]:
            return None
    return item


def _align_diagram_visual(visual: dict[str, Any], topic: str, task_title: str, scenario: str) -> dict[str, Any]:
    if str(visual.get("type") or "").lower() != "diagram":
        return visual
    out = dict(visual)
    spec = dict(out.get("diagram") or {}) if isinstance(out.get("diagram"), dict) else {}
    context = f"{topic} {task_title} {scenario} {out.get('title') or ''}"
    validated = validate_diagram_spec(spec, context=context, title=task_title or topic)
    out["diagram"] = validated.spec
    out["title"] = f"{topic}: физикалық сызба"
    out["validation_confidence"] = round(validated.confidence, 2)
    return out


def _humanize_visual_column(name: str) -> str:
    key = str(name or "").strip()
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
    low = key.lower()
    if low in known:
        return known[low]
    if "_" in key:
        return key.replace("_", " ").strip().capitalize()
    return key


def _normalize_pisa_visual(visual: Any, preference: str = "") -> dict[str, Any] | None:
    if not isinstance(visual, dict):
        return None
    vtype = str(visual.get("type") or "").strip().lower()
    preference = str(preference or "").strip().lower()
    allowed = {"table", "bar", "line", "diagram", "image"}
    if vtype not in allowed:
        return None
    if preference and vtype != preference:
        return None

    title = str(visual.get("title") or "Көрнекі дерек").strip()
    out: dict[str, Any] = {"type": vtype, "title": title}

    if vtype == "table":
        rows = visual.get("rows")
        if not isinstance(rows, list) or not rows:
            return None
        cleaned_rows = [r for r in rows if isinstance(r, dict) and r]
        if not cleaned_rows:
            return None
        raw_labels = visual.get("column_labels") if isinstance(visual.get("column_labels"), dict) else {}
        labels: dict[str, str] = {}
        for row in cleaned_rows:
            for key in row.keys():
                labels[str(key)] = str(raw_labels.get(str(key)) or _humanize_visual_column(str(key)))
        out.update({"rows": cleaned_rows, "column_labels": labels})
        return out

    if vtype in {"bar", "line"}:
        x, y = visual.get("x"), visual.get("y")
        if not isinstance(x, list) or not isinstance(y, list) or not x or len(x) != len(y):
            return None
        out.update({
            "x": x,
            "y": y,
            "x_label": str(visual.get("x_label") or "Көрсеткіш").strip(),
            "y_label": str(visual.get("y_label") or "Мән").strip(),
        })
        return out

    if vtype == "diagram":
        spec = visual.get("diagram") if isinstance(visual.get("diagram"), dict) else None
        if not spec:
            # Tolerate a model that placed diagram fields directly in visual.
            keys = {"diagram_type", "axes", "trajectory", "points", "vectors", "objects", "caption"}
            spec = {k: visual[k] for k in keys if k in visual}
        if not isinstance(spec, dict) or not spec:
            return None
        spec.setdefault("diagram_type", "generic")
        out["diagram"] = spec
        return out

    prompt = str(visual.get("prompt") or "").strip()
    if not prompt:
        return None
    out["prompt"] = prompt
    return out


def generate_pisa(
    ai: AIClient,
    grade: int,
    topic: str,
    *,
    mastery: float | None = None,
    avoid_titles: list[str] | None = None,
    learning_goal: str = "",
    visual_preference: str = "auto",
    status: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Generate a PISA task through a model-first visual planner.

    In automatic mode the model semantically chooses table/chart/physics
    diagram/context image/no-visual through function calling.  Manual selection
    remains available as an override for teachers.
    """
    if not ai.available:
        if status is not None:
            status["reason"] = "ЖИ қызметі қолжетімсіз. Қосылым мен баптауды тексеріңіз."
        return None
    avoid_titles = (avoid_titles or [])[-6:]
    mastery_text = f"{mastery:.0f}%" if mastery is not None else "белгісіз"
    requested_pref = str(visual_preference or "auto").strip().lower() or "auto"
    if requested_pref not in {"auto", "table", "bar", "line", "diagram", "image", "none"}:
        requested_pref = "auto"

    try:
        visual_plan = choose_pisa_visual(
            ai,
            grade=grade,
            topic=topic,
            learning_goal=learning_goal,
            preference=requested_pref,
        )
    except Exception:
        logger.exception("PISA visual planning failed")
        if status is not None:
            status["reason"] = "ЖИ көрнекілікті жоспарлай алмады. Қайта көріңіз."
        return None
    preference = visual_plan.visual_type

    system = """Сен физикадан PISA стиліндегі функционалдық сауаттылық тапсырмаларын құрастырушы сарапшысың.
Мұғалімнің еркін тілмен жазылған сұранысын мағынасы бойынша түсін; нақты тірек сөздерге байланба.
Тапсырма өмірлік шынайы жағдаятқа негізделсін, жеткілікті дерек берілсін, сұрақтар тек формула қоюды емес,
құбылысты түсіндіруді, деректі интерпретациялауды және дәлелдеуді тексерсін. Сандық есеп болса жауабы тексерілген болсын.
Кесте бағандары, график осьтері және барлық атаулар оқушыға түсінікті қазақ тілінде болсын. snake_case техникалық атауларды оқушыға көрсетпе.
Физикалық схема қажет болса ASCII символдарымен немесе сурет генераторындағы мәтінмен салма: diagram құрылымын бер.
Көрнекілік әшекей үшін емес: кемінде бір сұрақ оны пайдалануды немесе одан дерек алуды қажет етсін.
Жағдаят, көрнекілік және барлық 3 сұрақ мұғалім сұраған физика тақырыбына тікелей қатысты болуы міндетті. Басқа тарауға ауыспа.
Жауапты тек JSON объект ретінде бер."""

    visual_rule = {
        "table": "visual.type дәл table болсын. Кестеде сұрақтарды шешуге керекті нақты дерек болсын.",
        "bar": "visual.type дәл bar болсын. Категорияларды салыстыруға қажет сандық дерек бер.",
        "line": "visual.type дәл line болсын. Үздіксіз тәуелділік/уақыттық өзгеріс дерегін бер.",
        "diagram": "visual.type дәл diagram болсын. Вектор/траектория/сәуле/тізбек/объектілерді diagram объектісінде құрылымдап бер.",
        "image": "visual.type дәл image болсын. prompt өрісінде сурет ішінде мәтін, формула, сан, белгі жаздырмайтын контекстік иллюстрация сипаттамасын бер. Сұрақ суреттегі жалпы бақыланатын құбылыс/жағдайға сүйенсін.",
        "none": "visual мәні null болсын. Көрнекілік қоспа.",
    }[preference]

    base_user = f"""Сынып: {grade}
Мұғалімнің тақырыбы/еркін сұранысы: {topic}
Қосымша оқу мақсаты/талап: {learning_goal or 'тақырып бойынша функционалдық сауаттылықты тексеру'}
Оқушы mastery: {mastery_text}
Бұрынғы атауларды қайталама: {json.dumps(avoid_titles, ensure_ascii=False)}
Көрнекілік режимі: {requested_pref}
ЖИ таңдаған көрнекілік: {preference}
Неге/мақсаты: {visual_plan.reason or 'тапсырмаға ең пайдалы формат'}
Көрнекілікте міндетті түрде болуы тиіс дәлел/дерек: {visual_plan.instruction or 'кемінде бір сұраққа қажетті ақпарат'}
{visual_rule}

Бір жаңа PISA жағдаятын құр. Дәл 3 сұрақ болсын:
1) ақпаратты/ғылыми ұғымды қолдану;
2) есептеу немесе деректі интерпретациялау;
3) дәлелдеу/қорытынды жасау.
Контекст категориясының біреуін таңда: жеке өмір, мектеп, қоғам, ғылыми-техникалық.
Құзыреттіліктің біреуін таңда: құбылысты ғылыми түсіндіру, зерттеуді бағалау, деректерді интерпретациялау.
Күрделілік деңгейі 1-6 аралығы.

Көрнекілік форматтары:
- table: rows — объектілер массиві; column_labels — әр key үшін қазақша тақырып.
- bar/line: x және y ұзындықтары бірдей; x_label және y_label қазақша.
- diagram: diagram объектісі. Координаталар 0..100, x оңға, y жоғары; vectors: x,y,dx,dy,label; trajectory: [[x,y],...]; points және objects қажет болғанда ғана.
  diagram_type рұқсат етілген түрлері: linear_motion, accelerated_motion, free_fall, projectile_motion, circular_motion, rotating_platform, forces, inclined_plane, energy_conversion, momentum_collision, pressure_buoyancy, fluid_pressure, heat_transfer, phase_change, gas_process, oscillation, spring, wave, ray_optics, lens, mirror, electric_circuit, electric_field, magnetic_field, electromagnetic_induction, lever, pulley, measurement, generic_physics_scene. Координата осін тек физикалық қажет жағдайда ғана қолдан.
- image: prompt — сурет ішінде мәтін/формула/сан/сутаңба болмайтын қысқа сипаттама.
- none: visual = null.

JSON:
{{"id":"PISA-AI-...","grade":{grade},"topic":"...","title":"...","context_category":"...","competency":"...","pisa_level":4,
"scenario":"жағдаят және қажет деректер",
"visual":null немесе таңдалған форматтағы объект,
"questions":[{{"q":"...","type":"numeric|open","answer":"numeric болса нақты жауап","tolerance":0.02,"rubric":"бағалау шарты","sample_answer":"үлгі жауап"}}]}}"""

    try:
        data: dict[str, Any] | None = None
        visual: dict[str, Any] | None = None
        cleaned_q: list[dict[str, Any]] = []
        for attempt in range(5):
            suffix = ""
            if attempt == 1:
                suffix = (
                    f"\n\nАЛДЫҢҒЫ НӘТИЖЕНІ ҚАЙТАЛАМА. Тақырыптан ауытқыма. "
                    f"Көрнекілік дәл '{preference}' талабына сәйкес болсын және кемінде бір сұрақ оны пайдалануды қажет етсін."
                )
            if attempt >= 2:
                suffix = "\n\nАлдыңғы жауап толық болмады. Көрнекілікті null қалдыруға болады. Міндетті түрде үш толық сұрақ бер, тақырыптан ауытқыма."
            try:
                candidate = ai.json(system, base_user + suffix)
            except json.JSONDecodeError:
                if status is not None:
                    status["reason"] = "ЖИ жарамды JSON жауабын бермеді."
                logger.warning("PISA response was not valid JSON (attempt %s)", attempt + 1)
                continue
            except Exception as exc:
                if type(exc).__name__ not in {"APITimeoutError", "APIConnectionError", "RateLimitError", "InternalServerError"}:
                    raise
                if status is not None:
                    status["reason"] = "ЖИ қызметіне уақытша қосылу мүмкін болмады."
                logger.warning("Temporary PISA API failure on attempt %s: %s", attempt + 1, type(exc).__name__)
                continue
            if not isinstance(candidate, dict) or not str(candidate.get("scenario", "")).strip():
                if status is not None:
                    status["reason"] = "ЖИ жағдаятты толық бермеді."
                continue
            if not _scenario_matches_topic(topic, candidate) and not _scenario_semantically_matches_topic(ai, topic, candidate):
                if status is not None:
                    status["reason"] = "ЖИ берген жағдаят таңдалған тақырыпқа сәйкес келмеді."
                continue

            if preference == "none":
                candidate_visual = None
            else:
                candidate_visual = _normalize_pisa_visual(candidate.get("visual"), preference)
                if candidate_visual is None and attempt < 2:
                    if status is not None:
                        status["reason"] = "ЖИ берген көрнекілік жарамсыз болды."
                    continue
                if candidate_visual is not None:
                    candidate_visual = _align_diagram_visual(
                        candidate_visual,
                        topic,
                        str(candidate.get("title") or topic),
                        str(candidate.get("scenario") or ""),
                    )
            questions = candidate.get("questions")
            cleaned_q = []
            if isinstance(questions, list):
                for q in questions[:3]:
                    item = _clean_pisa_question(q)
                    if item is not None:
                        cleaned_q.append(item)
            if 0 < len(cleaned_q) < 3 and attempt >= 2:
                try:
                    missing = 3 - len(cleaned_q)
                    completion = ai.json(
                        system,
                        f"Тақырып: {topic}. Берілген өмірлік жағдаят: {candidate['scenario']}\n"
                        f"Бар сұрақтар: {json.dumps(cleaned_q, ensure_ascii=False)}\n"
                        f"Жетпейтін дәл {missing} БӨЛЕК сұрақты құрастыр. Тек JSON: "
                        '{"questions":[{"q":"...","type":"open|numeric","answer":"сандық болса",'
                        '"rubric":"...","sample_answer":"..."}]}.',
                    )
                    extra = completion.get("questions") if isinstance(completion, dict) else None
                    if isinstance(extra, list):
                        seen = {q["q"].casefold() for q in cleaned_q}
                        for q in extra:
                            item = _clean_pisa_question(q)
                            if item and item["q"].casefold() not in seen:
                                cleaned_q.append(item)
                                seen.add(item["q"].casefold())
                                if len(cleaned_q) == 3:
                                    break
                except Exception:
                    logger.warning("PISA question completion failed", exc_info=True)
            if len(cleaned_q) < 3:
                if status is not None:
                    status["reason"] = "ЖИ үш толық сұрақ бермеді."
                continue
            data, visual = candidate, candidate_visual
            break
        if not data:
            return None
        try:
            level = int(data.get("pisa_level", 4) or 4)
        except (TypeError, ValueError):
            level = 4

        result: dict[str, Any] = {
            "id": str(data.get("id") or f"PISA-AI-{uuid.uuid4().hex[:8].upper()}"),
            "grade": grade,
            "topic": topic.strip(),
            "title": str(data.get("title") or f"{topic}: PISA жағдаяты").strip(),
            "context_category": str(data.get("context_category") or "қоғам").strip(),
            "competency": str(data.get("competency") or "деректерді интерпретациялау").strip(),
            "pisa_level": max(1, min(6, level)),
            "scenario": str(data.get("scenario", "")).strip(),
            "questions": cleaned_q,
            "visual": visual,
            "visual_mode": requested_pref,
            "visual_selected": preference,
            "source": "generated",
        }
        if status is not None:
            status.pop("reason", None)
        return result
    except Exception:
        logger.exception("PISA task generation failed")
        if status is not None:
            status["reason"] = "ЖИ қызметімен байланыс кезінде қате шықты. Қызмет баптауын және сервер журналын тексеріңіз."
        return None
