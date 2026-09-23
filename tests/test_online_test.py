"""Run with python -m unittest tests.test_online_test."""
import sys
import tempfile
import types
import unittest
from pathlib import Path

try:
    import dotenv
except ModuleNotFoundError:
    sys.modules["dotenv"] = types.SimpleNamespace(load_dotenv=lambda **kwargs: None)

from core.database import Database
from ai.question_generator import _scenario_matches_topic, generate_assignment_tasks, generate_pisa
from ai_core.router import ToolRouter


class OnlineTestFlow(unittest.TestCase):
    def test_pisa_retries_incomplete_questions(self):
        class StubAI:
            available = True
            calls = 0
            def tool_plan(self, *args, **kwargs):
                return {"calls": [{"name": "no_visual", "arguments": {}}]}
            def json(self, *args, **kwargs):
                self.calls += 1
                questions = [{"q": f"Қозғалыс туралы {i}?", "type": "open", "sample_answer": "Жауап"}
                             for i in range(2 if self.calls == 1 else 3)]
                return {"scenario": "Көлік қозғалысының жылдамдығы өзгерді.", "visual": None, "questions": questions}
        ai = StubAI()
        task = generate_pisa(ai, 9, "Кинематика", visual_preference="none")
        self.assertEqual(ai.calls, 2)
        self.assertEqual(len(task["questions"]), 3)

    def test_assignment_batches_make_requested_count(self):
        class StubAI:
            available = True
            calls = 0
            def json(self, *args, **kwargs):
                self.calls += 1
                return {"questions": [{"question": f"Қозғалыс есеп {self.calls}-{i}",
                                        "answer": "5", "solution": "2+3=5"} for i in range(6)]}
        ai = StubAI()
        tasks = generate_assignment_tasks(ai, 9, "Кинематика", "B", 17)
        self.assertEqual(len(tasks), 17)
        self.assertEqual(ai.calls, 3)

    def test_pisa_kinematics_after_unusable_visual(self):
        class StubAI:
            available=True
            def __init__(self): self.calls=0
            def tool_plan(self,*args,**kwargs):
                return {"calls":[{"name":"use_context_image","arguments":{"reason":"өмірлік жағдаят","instruction":"автобус"}}]}
            def json(self,*args,**kwargs):
                self.calls+=1
                task={"title":"Автобустың қозғалысы","scenario":"Автобус 10 м/с жылдамдықпен қозғалды.",
                    "questions":[{"q":"Уақытты тап","type":"numeric","answer":"5"},
                                 {"q":"Қашықтықты тап","type":"numeric","answer":"50"},
                                 {"q":"Нәтижені түсіндір","type":"open","rubric":"Дәлел"}]}
                if self.calls<3: task["visual"]={"type":"image"}  # Missing prompt.
                else: task["visual"]=None
                return task
        client=StubAI()
        task=generate_pisa(client,9,"Кинематика")
        self.assertIsNotNone(task)
        self.assertEqual(client.calls,3)
        self.assertEqual(task["topic"],"Кинематика")

    def test_kinematics_topic_and_picture_routing(self):
        self.assertTrue(_scenario_matches_topic("Кинематика",{"scenario":"Автобус уақытқа қарай жылдамдығын өзгертіп қозғалады.","questions":[]}))
        self.assertIn("create_image",ToolRouter().plan("Еркін түсу туралы сурет салып бер").tools)
        self.assertNotIn("create_diagram",ToolRouter().plan("Еркін түсу туралы сурет салып бер").tools)
        self.assertIn("create_diagram",ToolRouter().plan("Күштің векторлық сызбасын сал").tools)

    def test_pisa_semantic_paraphrase(self):
        class StubAI:
            available = True
            def __init__(self, relevant):
                self.relevant = relevant
                self.topic_checks = 0
            def tool_plan(self, *args, **kwargs):
                return {"calls": [{"name": "no_visual", "arguments": {}}]}
            def json(self, system, user):
                if "тәуелсіз тексересің" in system:
                    self.topic_checks += 1
                    return {"relevant": self.relevant}
                return {"title": "Су бетіндегі сәуле", "scenario": "Сәуле ауадан суға өткенде бағытын өзгертеді.",
                        "visual": None, "questions": [
                            {"q": "Сәуленің бағыты неге өзгереді?", "type": "open"},
                            {"q": "Бұрыштарды салыстырыңыз.", "type": "open"},
                            {"q": "Нәтижені түсіндіріңіз.", "type": "open"}]}
        accepted = StubAI(True)
        self.assertIsNotNone(generate_pisa(accepted, 8, "Жарықтың сынуы", visual_preference="none"))
        self.assertEqual(accepted.topic_checks, 1)
        rejected = StubAI(False)
        self.assertIsNone(generate_pisa(rejected, 8, "Жарықтың сынуы", visual_preference="none"))
        self.assertEqual(rejected.topic_checks, 5)

    def test_membership_video_access_and_one_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            db=Database(Path(directory)/"school.db")
            teacher=db.register_user("teacher","secret","Мұғалім","teacher")
            stranger=db.register_user("stranger","secret","Басқа мұғалім","teacher")
            student=db.register_user("student","secret","Оқушы","student",9)
            outsider=db.register_user("outsider","secret","Басқа оқушы","student",9)
            klass=db.create_class(teacher,"9А")
            db.join_class(student,klass["join_code"])
            task={"question":"Қашықтық неге тең?","answer":"120","type":"numeric","topic":"Кинематика"}
            aid=db.create_assignment(teacher,klass["id"],"Кинематика","Кинематика","B",[task,task])
            db.set_assignment_delivery_mode(aid,teacher,"online_test")
            items=db.assignment_items(aid)
            with self.assertRaises(ValueError):
                db.start_online_test(aid,outsider)
            db.start_online_test(aid,student)
            video=b"\x1a\x45\xdf\xa3example-video"
            db.save_online_test_answer(aid,student,items[0]["id"],"120",True,18,video,"video/webm")
            with self.assertRaises(ValueError):
                db.finish_online_test(aid,student)
            with self.assertRaises(Exception):
                db.save_online_test_answer(aid,student,items[0]["id"],"120",True,1,video,"video/webm")
            db.save_online_test_answer(aid,student,items[1]["id"],"100",False,31,video,"video/webm")
            db.finish_online_test(aid,student)
            self.assertIsNone(db.online_test_report(aid,student,stranger,include_video=True))
            self.assertIsNone(db.online_test_report(aid,outsider,include_video=True))
            report=db.online_test_report(aid,student,teacher,include_video=True)
            self.assertEqual([r["is_correct"] for r in report["answers"]],[1,0])
            self.assertEqual(report["answers"][0]["video_data"],video)
            self.assertEqual(len(db.student_online_test_reports(student)),1)
            self.assertEqual(len(db.teacher_online_test_reports(aid,stranger)),0)
            with self.assertRaises(ValueError):
                db.save_online_test_answer(aid,student,items[1]["id"],"120",True,1,video,"video/webm")
