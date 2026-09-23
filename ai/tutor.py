from __future__ import annotations

from ai.openai_client import AIClient
from ai.prompt_builder import TUTOR_SYSTEM, build_student_context


def tutor_reply(ai: AIClient, user, mastery, mistakes, recent, question: str, rag_context: str = "") -> str:
    context = build_student_context(user, mastery, mistakes, recent)
    source = f"\n\nОҚУ МАТЕРИАЛЫНАН ҮЗІНДІЛЕР:\n{rag_context}" if rag_context else ""
    if not ai.available:
        return "ЖИ мұғалім қызметі уақытша қолжетімсіз. Кейінірек қайта көріңіз немесе мұғалімге хабарласыңыз."
    return ai.text(TUTOR_SYSTEM, f"{context}{source}\n\nОқушы сұрағы: {question}")
