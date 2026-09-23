from __future__ import annotations

from typing import Any


def build_student_context(user: dict[str, Any], mastery: list[dict[str, Any]], mistakes: list[dict[str, Any]], recent: list[dict[str, Any]]) -> str:
    mlines = "\n".join(
        f"- {r['topic']}: {float(r.get('score', 50)):.0f}% (әрекет саны: {int(r.get('attempts', 0))})"
        for r in mastery[:12]
    ) or "- Мәлімет әлі жоқ"
    elines = "\n".join(
        f"- {m['topic']} / {m['mistake_type']}: {m['description']} (қайталануы {m['frequency']} рет)"
        for m in mistakes[:8]
    ) or "- Қайталанатын қате тіркелмеген"
    rlines = "\n".join(
        f"- {a['topic']}: {'дұрыс' if a.get('is_correct') else 'қате'}, деңгей {a.get('difficulty') or '-'}"
        for a in recent[:6]
    ) or "- Соңғы әрекет жоқ"
    return f"""
ОҚУШЫ КОНТЕКСТІ
Аты: {user.get('full_name')}
Сынып: {user.get('grade') or 'көрсетілмеген'}

Тақырыптық меңгеру:
{mlines}

Қайталанатын қателер:
{elines}

Соңғы әрекеттер:
{rlines}
""".strip()


TUTOR_SYSTEM = """Сен Қазақстан мектебіндегі физика пәніне арналған AI Physics KZ цифрлық ұстазысың.
Мақсатың — дайын жауапты бірден айту емес, оқушыны түсінуге және өз бетімен шешуге жетелеу.
Қазақ тілінде анық, жас ерекшелігіне сай жауап бер. Физикалық формулаларды дұрыс жаз, SI бірліктерін тексер.
Оқушы қиналса: қысқа түсіндіру → жетекші сұрақ → ұқсас мысал → тек содан кейін толық шешім.
Оқушы жақсы меңгерсе, күрделілікті арттыр. Қайталанатын қатені байқасаң, оны нақты атап, түзету тапсырмасын ұсын.
Белгісіз фактіні ойдан қоспа. Берілген оқу материалының үзінділері болса, соған басымдық бер."""
