"""A login survives a new application session and can be revoked or expire."""
from pathlib import Path
from tempfile import TemporaryDirectory

from core.database import Database


def test_browser_session_is_restored_and_revoked():
    with TemporaryDirectory() as directory:
        path = Path(directory) / "users.db"
        db = Database(path)
        for role in ("teacher", "student"):
            uid = db.register_user(role, "password123", role, role, 9 if role == "student" else None)
            token = db.create_auth_session(uid)
            assert db.user_from_auth_session(token)["role"] == role
            assert Database(path).user_from_auth_session(token)["id"] == uid
            db.revoke_auth_session(token)
            assert db.user_from_auth_session(token) is None


def test_expired_session_is_rejected():
    with TemporaryDirectory() as directory:
        db = Database(Path(directory) / "users.db")
        uid = db.register_user("student", "password123", "Student", "student", 9)
        token = db.create_auth_session(uid, days=-1)
        assert db.user_from_auth_session(token) is None
        assert db.user_from_auth_session("invalid") is None
