"""Check AI descriptors and server-side rubric totals without starting Streamlit."""
import ast
import json
import sys
import types
import unittest
from pathlib import Path
from typing import Any

try:
    import dotenv
except ModuleNotFoundError:
    sys.modules["dotenv"] = types.SimpleNamespace(load_dotenv=lambda **kwargs: None)

from ai.question_generator import clean_descriptors, generate_descriptors


class DescriptorFlow(unittest.TestCase):
    def test_ai_proposes_concrete_points(self):
        class AI:
            available = True
            def json(self, *args):
                return {"descriptors": [{"description": "Формуланы қолданады", "points": 2},
                                        {"description": "Жауапты жазады", "points": 1}]}
        self.assertEqual(sum(d["points"] for d in generate_descriptors(AI(), 9, "Есеп", "5", "Шешуі")), 3)
        self.assertEqual(clean_descriptors([{"description": "", "points": 1},
                                           {"description": "Жалған", "points": -3}]), [])

    def test_notebook_total_comes_from_confirmed_descriptors(self):
        source = Path(__file__).resolve().parents[1].joinpath("app.py").read_text()
        function = next(node for node in ast.parse(source).body
                        if isinstance(node, ast.FunctionDef) and node.name == "analyze_notebook_submission")
        ns = {"AIClient": object, "Any": Any, "json": json, "clean_descriptors": clean_descriptors}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "app.py", "exec"), ns)

        class AI:
            available = True
            def vision_json(self, *args):
                return {"score": 100, "answers": [{"question_index": 1, "student_answer": "F=ma",
                    "descriptors": [{"index": 1, "awarded_points": 99, "evidence": "Формула бар"},
                                    {"index": 2, "awarded_points": 0, "evidence": "Жауабы жоқ"}]}]}

        assignment = {"topic": "Күш", "difficulty": "B"}
        items = [{"task": {"question": "Күшті тап", "answer": "6 Н", "solution": "F=ma=6 Н",
                           "descriptors": [{"description": "Формула", "points": 1},
                                           {"description": "Жауап", "points": 2}]}}]
        result = ns["analyze_notebook_submission"](AI(), assignment, items, b"photo", "image/png")
        self.assertTrue(result["graded"])
        self.assertAlmostEqual(result["score"], 100 / 3)
        self.assertIn("1/3 балл", result["feedback"])


if __name__ == "__main__":
    unittest.main()
