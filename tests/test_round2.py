"""Run with: python -m unittest tests.test_round2"""
import tempfile
import unittest
import sys
import types
from pathlib import Path

# The test runtime does not need environment-file loading.
try:
    import dotenv
except ModuleNotFoundError:
    sys.modules["dotenv"] = types.SimpleNamespace(load_dotenv=lambda **kwargs: None)

from ai.assessment import numeric_answer_matches
from core.database import Database
from reports.learning_evidence import paired_diagnostics


class Round2Tests(unittest.TestCase):
    def test_numeric_answer_checks_unit(self):
        self.assertTrue(numeric_answer_matches("10 м/с", "10 м/с"))
        self.assertFalse(numeric_answer_matches("10 м/с", "10 км/сағ"))
        self.assertFalse(numeric_answer_matches("10 м/с", "10"))
        self.assertFalse(numeric_answer_matches("10", "10 м"))

    def test_comparison_requires_same_topic_and_count(self):
        runs = [
            {"id": 1, "focus_topic": "Жылдамдық", "phase": "baseline", "percent": 40, "total": 10, "created_at": "2026-09-01"},
            {"id": 2, "focus_topic": "Жылдамдық", "phase": "final", "percent": 80, "total": 8, "created_at": "2026-09-02"},
            {"id": 3, "focus_topic": "Жылдамдық", "phase": "final", "percent": 70, "total": 10, "created_at": "2026-09-03"},
        ]
        # A non-equivalent final test must not consume the baseline.
        results = paired_diagnostics(runs)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["Өзгеріс (п.т.)"], 30)

    def test_mistake_requires_successful_correction_and_owner(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / "test.db")
            student = db.register_user("test_student", "password", "Оқушы", "student", 9)
            other = db.register_user("other_student", "password", "Басқа", "student", 9)
            db.record_mistake(student, "Жылдамдық", "UNIT_ERROR", "Бірлік")
            mistake = db.get_mistakes(student)[0]
            self.assertFalse(db.resolve_mistake(mistake["id"], other))
            self.assertFalse(db.resolve_mistake(mistake["id"], student))
            db.log_attempt(student_id=student, activity_type="adaptive", topic="Жылдамдық",
                           question_text="Бірлікті түзет", student_answer="м/с", is_correct=1)
            self.assertTrue(db.resolve_mistake(mistake["id"], student))
            self.assertEqual(db.get_mistakes(student), [])

    def test_teacher_can_grade_pending_pisa_once(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / "test.db")
            teacher = db.register_user("teacher", "password", "Мұғалім", "teacher")
            stranger = db.register_user("stranger", "password", "Басқа мұғалім", "teacher")
            student = db.register_user("student", "password", "Оқушы", "student", 9)
            group = db.create_class(teacher, "9А")
            db.join_class(student, group["join_code"])
            assignment = db.create_pisa_assignment(teacher, group["id"], "Тақырып", "Жылдамдық", {"questions": []})
            db.submit_pisa_response(assignment, student, 1, "Сұрақ", "Жауап", "Үлгі", None, None, "Күтуде")
            response = db.teacher_pisa_results(assignment, teacher)[0]
            self.assertIsNone(response["score"])
            self.assertFalse(db.grade_pisa_response(response["id"], stranger, True, ""))
            self.assertTrue(db.grade_pisa_response(response["id"], teacher, True, "Дәлел дұрыс"))
            self.assertFalse(db.grade_pisa_response(response["id"], teacher, True, "Қайта баға"))
            self.assertEqual(db.teacher_pisa_results(assignment, teacher)[0]["score"], 100)


if __name__ == "__main__":
    unittest.main()
