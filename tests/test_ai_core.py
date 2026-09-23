from pathlib import Path

import pytest

from ai_core.files import safe_display_name, validate_upload
from ai_core.permissions import PermissionManager
from ai_core.router import ToolRouter
from core.database import Database


def test_conversation_history_and_ownership(tmp_path: Path):
    db = Database(tmp_path / "db.sqlite")
    teacher = db.register_user("teacher_ai", "secret1", "Teacher", "teacher")
    other = db.register_user("other_ai", "secret1", "Other", "teacher")
    cid = db.create_conversation(teacher, "teacher")
    db.add_message(cid, teacher, "user", "Еркін түсуге ҚМЖ жаса")
    db.add_message(cid, teacher, "assistant", "ҚМЖ дайын")
    assert [m["sender"] for m in db.messages(cid, teacher)] == ["user", "assistant"]
    assert db.conversation(cid, teacher)["title"].startswith("Еркін түсуге")
    with pytest.raises(PermissionError):
        db.messages(cid, other)


def test_role_permissions_are_server_side():
    assert PermissionManager.allowed("teacher", "get_class_results")
    assert not PermissionManager.allowed("student", "get_class_results")
    assert not PermissionManager.allowed("student", "assign_task")
    with pytest.raises(PermissionError):
        PermissionManager.require("student", "create_kmj")


def test_multi_tool_routing_and_exact_slide_count():
    plan = ToolRouter().plan("9-сыныпқа ҚМЖ жаса, содан кейін 7 слайд презентация және фон жаса")
    assert plan.tools == ["create_kmj", "create_pptx", "create_image_background"]
    assert plan.slide_count == 7


def test_student_image_routes_to_vision():
    plan = ToolRouter().plan("Мына дәптер фотосынан қатемді тап", has_attachment=True)
    assert plan.tools[0] == "vision"


def test_upload_validation_and_path_sanitizing():
    assert safe_display_name("../../есеп<script>.pdf") == "есеп_script_.pdf"
    validate_upload("есеп.pdf", "application/pdf", 100)
    with pytest.raises(ValueError):
        validate_upload("virus.exe", "application/octet-stream", 100)
    with pytest.raises(ValueError):
        validate_upload("huge.pdf", "application/pdf", 21 * 1024 * 1024, 20)
