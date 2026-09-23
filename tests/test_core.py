from pathlib import Path
import tempfile

from adaptive.engine import AdaptiveEngine
from adaptive.spaced_repetition import next_state, quality_from_result
from core.database import Database
from rag.document_loader import chunk_text
from rag.retrieval import retrieve


def test_adaptive_levels():
    assert AdaptiveEngine.level_from_mastery(20) == "A"
    assert AdaptiveEngine.level_from_mastery(60) == "B"
    assert AdaptiveEngine.level_from_mastery(90) == "C"


def test_spaced_repetition():
    q = quality_from_result(True, 5, "B")
    state = next_state(None, q)
    assert state["interval_days"] >= 1
    assert state["repetition_count"] == 1


def test_database_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        db = Database(Path(d) / "test.db")
        uid = db.register_user("student", "secret1", "Test Student", "student", 9, "Ә")
        auth = db.authenticate("student", "secret1")
        assert auth["id"] == uid
        assert auth["grade"] == 9
        assert auth["class_letter"] == "Ә"
        db.ensure_topics(uid, 9, ["Импульс"])
        result = db.update_mastery(uid, 9, "Импульс", True)
        assert result["attempts"] == 1


def test_rag():
    chunks = [
        {"content":"Импульс дене массасы мен жылдамдықтың көбейтіндісіне тең.","title":"Физика","chunk_index":0},
        {"content":"Жылу мөлшері Q=cmΔT формуласымен есептеледі.","title":"Физика","chunk_index":1},
    ]
    results = retrieve("импульс масса жылдамдық", chunks, 1)
    assert results and "Импульс" in results[0]["content"]


def test_chunk_text():
    text = "Физика ғылымы. " * 300
    chunks = chunk_text(text, 300, 40)
    assert len(chunks) > 2


def test_join_class_syncs_grade_and_letter():
    with tempfile.TemporaryDirectory() as d:
        db = Database(Path(d) / "test.db")
        teacher = db.register_user("teacher", "secret1", "Teacher", "teacher")
        student = db.register_user("student2", "secret1", "Student", "student", 8, "Б")
        cls = db.create_class(teacher, "9А")
        name = db.join_class(student, cls["join_code"])
        user = db.get_user(student)
        assert name == "9А"
        assert user["grade"] == 9
        assert user["class_letter"] == "А"


def test_rag_class_isolation():
    with tempfile.TemporaryDirectory() as d:
        db = Database(Path(d) / "test.db")
        t1 = db.register_user("t1", "secret1", "Teacher One", "teacher")
        t2 = db.register_user("t2", "secret1", "Teacher Two", "teacher")
        s1 = db.register_user("s1", "secret1", "Student One", "student", 9, "А")
        s2 = db.register_user("s2", "secret1", "Student Two", "student", 9, "Б")
        c1 = db.create_class(t1, "9А")
        c2 = db.create_class(t2, "9Б")
        db.join_class(s1, c1["join_code"])
        db.join_class(s2, c2["join_code"])
        d1 = db.add_document(t1, "one.txt", "One", ["Only class A material"])
        d2 = db.add_document(t2, "two.txt", "Two", ["Only class B material"])
        db.assign_document_to_classes(d1, t1, [c1["id"]])
        db.assign_document_to_classes(d2, t2, [c2["id"]])
        chunks1 = db.accessible_chunks_for_student(s1)
        chunks2 = db.accessible_chunks_for_student(s2)
        assert [x["title"] for x in chunks1] == ["One"]
        assert [x["title"] for x in chunks2] == ["Two"]


def test_assignment_roundtrip_and_access_control():
    with tempfile.TemporaryDirectory() as d:
        db = Database(Path(d) / "test.db")
        teacher = db.register_user("teacher_a", "secret1", "Teacher", "teacher")
        student = db.register_user("student_a", "secret1", "Student", "student", 9, "А")
        outsider = db.register_user("student_b", "secret1", "Outsider", "student", 9, "Б")
        cls = db.create_class(teacher, "9А")
        db.join_class(student, cls["join_code"])
        task = {
            "id": "T1", "grade": 9, "topic": "Импульс", "difficulty": "A",
            "type": "numeric", "question": "2+2?", "answer": "4", "solution": "2+2=4",
            "error_hint": "CALCULATION_ERROR",
        }
        aid = db.create_assignment(teacher, cls["id"], "Test", "Импульс", "A", [task])
        rows = db.student_assignments(student)
        assert rows and rows[0]["id"] == aid
        assert not db.student_assignments(outsider)
        item = db.assignment_items(aid)[0]
        db.submit_assignment_item(student, aid, item["id"], "4", True, 100, "Дұрыс")
        submissions = db.assignment_submissions(student, aid)
        assert submissions and submissions[0]["score"] == 100
        try:
            db.submit_assignment_item(outsider, aid, item["id"], "4", True, 100, "Дұрыс")
            assert False, "outsider must not be able to submit"
        except ValueError:
            pass


def test_student_registration_requires_valid_class_code():
    with tempfile.TemporaryDirectory() as d:
        db = Database(Path(d) / "test.db")
        teacher = db.register_user("teacher_code", "secret1", "Teacher", "teacher")
        cls = db.create_class(teacher, "9Ә")
        try:
            db.register_student_with_class("no_code", "secret1", "No Code", "")
            assert False, "empty code must be rejected"
        except ValueError:
            pass
        try:
            db.register_student_with_class("bad_code", "secret1", "Bad Code", "WRONG")
            assert False, "invalid code must be rejected"
        except ValueError:
            pass
        student, name = db.register_student_with_class("good_code", "secret1", "Good Student", cls["join_code"])
        assert name == "9Ә"
        assert db.get_user(student)["class_letter"] == "Ә"


def test_assignment_history_keeps_every_submission():
    with tempfile.TemporaryDirectory() as d:
        db = Database(Path(d) / "test.db")
        teacher = db.register_user("teacher_hist", "secret1", "Teacher", "teacher")
        cls = db.create_class(teacher, "9А")
        student, _ = db.register_student_with_class("student_hist", "secret1", "Student History", cls["join_code"])
        task = {"id":"T1","question":"1+1?","answer":"2","solution":"1+1=2","type":"numeric"}
        aid = db.create_assignment(teacher, cls["id"], "History", "Кинематика", "A", [task])
        item = db.assignment_items(aid)[0]
        db.submit_assignment_item(student, aid, item["id"], "3", False, 0, "Қате")
        db.submit_assignment_item(student, aid, item["id"], "2", True, 100, "Дұрыс")
        hist = db.student_assignment_history(student)
        assert len(hist) == 2
        assert hist[0]["student_answer"] == "2"
        assert hist[1]["student_answer"] == "3"


def test_teacher_pisa_assignment_and_assistant_history():
    with tempfile.TemporaryDirectory() as d:
        db = Database(Path(d) / "test.db")
        teacher = db.register_user("teacher_pisa", "secret1", "Teacher", "teacher")
        cls = db.create_class(teacher, "9Б")
        student, _ = db.register_student_with_class("student_pisa", "secret1", "PISA Student", cls["join_code"])
        task = {
            "title":"PISA Test", "scenario":"Өмірлік жағдай", "questions":[
                {"q":"Неге?","type":"open","sample_answer":"Себебі","rubric":"Себебін түсіндіреді"}
            ]
        }
        pid = db.create_pisa_assignment(teacher, cls["id"], "PISA Test", "Қозғалыс", task)
        rows = db.student_pisa_assignments(student)
        assert rows and rows[0]["id"] == pid
        db.submit_pisa_response(pid, student, 1, "Неге?", "Себебі", "Себебі", True, 100, "Дұрыс")
        results = db.teacher_pisa_results(pid, teacher)
        assert results and results[0]["full_name"] == "PISA Student"
        db.add_assistant_message(teacher, "user", "ҚМЖ жаса")
        db.add_assistant_message(teacher, "assistant", "Дайын")
        hist = db.assistant_history(teacher)
        assert [x["role"] for x in hist] == ["user", "assistant"]
