from __future__ import annotations


TEACHER_TOOLS = {
    "chat", "vision", "analyze_file", "web_search", "code_execution", "create_kmj",
    "create_bjb", "create_tjb", "create_pisa", "create_worksheet", "create_test",
    "create_docx", "create_pdf", "create_pptx", "create_image", "create_image_background",
    "create_diagram", "create_chart", "get_student_history", "get_class_results", "assign_task",
}
STUDENT_TOOLS = {
    "chat", "vision", "analyze_file", "web_search", "code_execution", "create_diagram",
    "create_chart", "create_image", "get_own_history",
}


class PermissionManager:
    @staticmethod
    def allowed(role: str, tool: str) -> bool:
        return tool in (TEACHER_TOOLS if role == "teacher" else STUDENT_TOOLS if role == "student" else set())

    @classmethod
    def require(cls, role: str, tool: str) -> None:
        if not cls.allowed(role, tool):
            raise PermissionError("Бұл әрекет сіздің рөліңізге қолжетімсіз")
