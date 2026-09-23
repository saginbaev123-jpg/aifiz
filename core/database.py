from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from config import DB_PATH, PBKDF2_ITERATIONS


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iters, salt_hex, digest_hex = encoded.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iters),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


class Database:
    def __init__(self, path: Path | str = DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def init_schema(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('student','teacher')),
            grade INTEGER,
            class_letter TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            join_code TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            FOREIGN KEY(teacher_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS class_members (
            class_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            joined_at TEXT NOT NULL,
            PRIMARY KEY(class_id, student_id),
            FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS mastery (
            student_id INTEGER NOT NULL,
            grade INTEGER NOT NULL,
            topic TEXT NOT NULL,
            score REAL NOT NULL DEFAULT 50,
            confidence REAL NOT NULL DEFAULT 20,
            attempts INTEGER NOT NULL DEFAULT 0,
            correct INTEGER NOT NULL DEFAULT 0,
            last_practiced TEXT,
            PRIMARY KEY(student_id, grade, topic),
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,
            topic TEXT NOT NULL,
            difficulty TEXT,
            question_id TEXT,
            question_text TEXT NOT NULL,
            student_answer TEXT,
            correct_answer TEXT,
            is_correct INTEGER,
            confidence INTEGER,
            score REAL,
            error_type TEXT,
            feedback TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS diagnostic_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            grade INTEGER NOT NULL,
            total INTEGER NOT NULL,
            correct INTEGER NOT NULL,
            percent REAL NOT NULL,
            topic_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS mistakes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            mistake_type TEXT NOT NULL,
            description TEXT NOT NULL,
            frequency INTEGER NOT NULL DEFAULT 1,
            resolved INTEGER NOT NULL DEFAULT 0,
            last_seen TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS review_state (
            student_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            easiness REAL NOT NULL DEFAULT 2.5,
            interval_days INTEGER NOT NULL DEFAULT 0,
            repetition_count INTEGER NOT NULL DEFAULT 0,
            next_review TEXT,
            last_quality INTEGER,
            last_reviewed TEXT,
            PRIMARY KEY(student_id, topic),
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            topic TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(teacher_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS document_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS document_classes (
            document_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL,
            PRIMARY KEY(document_id, class_id),
            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            instructions TEXT,
            topic TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            due_at TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            FOREIGN KEY(teacher_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS assignment_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            task_json TEXT NOT NULL,
            FOREIGN KEY(assignment_id) REFERENCES assignments(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS assignment_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            student_answer TEXT,
            task_json TEXT,
            is_correct INTEGER,
            score REAL,
            feedback TEXT,
            submitted_at TEXT NOT NULL,
            UNIQUE(item_id, student_id),
            FOREIGN KEY(assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
            FOREIGN KEY(item_id) REFERENCES assignment_items(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS assignment_work_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            image_data BLOB NOT NULL,
            mime_type TEXT NOT NULL,
            ai_feedback TEXT,
            score REAL NOT NULL DEFAULT 0,
            submitted_at TEXT NOT NULL,
            UNIQUE(assignment_id, student_id),
            FOREIGN KEY(assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS assignment_submission_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            student_answer TEXT,
            is_correct INTEGER,
            score REAL,
            feedback TEXT,
            submitted_at TEXT NOT NULL,
            FOREIGN KEY(assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
            FOREIGN KEY(item_id) REFERENCES assignment_items(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS assignment_work_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            image_data BLOB NOT NULL,
            mime_type TEXT NOT NULL,
            ai_feedback TEXT,
            score REAL NOT NULL DEFAULT 0,
            submitted_at TEXT NOT NULL,
            FOREIGN KEY(assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS pisa_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            topic TEXT NOT NULL,
            task_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            FOREIGN KEY(teacher_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS pisa_assignment_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pisa_assignment_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            question_index INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            student_answer TEXT,
            correct_answer TEXT,
            is_correct INTEGER,
            score REAL,
            feedback TEXT,
            submitted_at TEXT NOT NULL,
            FOREIGN KEY(pisa_assignment_id) REFERENCES pisa_assignments(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS assistant_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            artifact_type TEXT,
            artifact_name TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('student','teacher')),
            title TEXT NOT NULL DEFAULT 'Жаңа чат',
            summary TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender TEXT NOT NULL CHECK(sender IN ('user','assistant','system')),
            text TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'completed',
            created_at TEXT NOT NULL,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(message_id) REFERENCES messages(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tool_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            message_id INTEGER,
            tool_name TEXT NOT NULL,
            arguments_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL,
            result_reference TEXT,
            duration_ms INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
            FOREIGN KEY(message_id) REFERENCES messages(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS generated_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            type TEXT NOT NULL,
            path TEXT NOT NULL,
            creator INTEGER NOT NULL,
            conversation_id INTEGER NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY(creator) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tool_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_call_id INTEGER NOT NULL,
            result_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY(tool_call_id) REFERENCES tool_calls(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            conversation_id INTEGER,
            kind TEXT NOT NULL,
            status TEXT NOT NULL,
            progress_text TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            result_json TEXT,
            error_text TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            metadata_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_attempts_student_created ON attempts(student_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_mastery_student_grade ON mastery(student_id, grade);
        CREATE INDEX IF NOT EXISTS idx_class_members_student ON class_members(student_id);
        CREATE INDEX IF NOT EXISTS idx_doc_classes_class ON document_classes(class_id);
        CREATE INDEX IF NOT EXISTS idx_assignments_class_status ON assignments(class_id, status);
        CREATE INDEX IF NOT EXISTS idx_submissions_student ON assignment_submissions(student_id, assignment_id);
        CREATE INDEX IF NOT EXISTS idx_assignment_hist_student ON assignment_submission_history(student_id, assignment_id);
        CREATE INDEX IF NOT EXISTS idx_work_hist_student ON assignment_work_history(student_id, assignment_id);
        CREATE INDEX IF NOT EXISTS idx_pisa_assignments_class ON pisa_assignments(class_id, status);
        CREATE INDEX IF NOT EXISTS idx_pisa_submissions_student ON pisa_assignment_submissions(student_id, pisa_assignment_id);
        CREATE INDEX IF NOT EXISTS idx_assistant_messages_user ON assistant_messages(user_id, id);
        CREATE INDEX IF NOT EXISTS idx_conversations_user_updated ON conversations(user_id, updated_at);
        CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id);
        CREATE INDEX IF NOT EXISTS idx_generated_conversation ON generated_files(conversation_id, id);
        """
        with self.connect() as con:
            con.executescript(schema)
            # Lightweight migration for databases created by earlier versions.
            user_cols = {row["name"] for row in con.execute("PRAGMA table_info(users)").fetchall()}
            if "class_letter" not in user_cols:
                con.execute("ALTER TABLE users ADD COLUMN class_letter TEXT")
            hist_cols = {row["name"] for row in con.execute("PRAGMA table_info(assignment_submission_history)").fetchall()}
            if "task_json" not in hist_cols:
                con.execute("ALTER TABLE assignment_submission_history ADD COLUMN task_json TEXT")
            diag_cols = {row["name"] for row in con.execute("PRAGMA table_info(diagnostic_runs)").fetchall()}
            if "focus_topic" not in diag_cols:
                con.execute("ALTER TABLE diagnostic_runs ADD COLUMN focus_topic TEXT")
            if "phase" not in diag_cols:
                con.execute("ALTER TABLE diagnostic_runs ADD COLUMN phase TEXT")
            assignment_cols = {row["name"] for row in con.execute("PRAGMA table_info(assignments)").fetchall()}
            if "delivery_mode" not in assignment_cols:
                con.execute("ALTER TABLE assignments ADD COLUMN delivery_mode TEXT NOT NULL DEFAULT 'notebook'")
            con.executescript("""
                CREATE TABLE IF NOT EXISTS online_test_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    UNIQUE(assignment_id,student_id),
                    FOREIGN KEY(assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
                    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS online_test_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    item_id INTEGER NOT NULL,
                    answer TEXT NOT NULL,
                    is_correct INTEGER NOT NULL,
                    duration_seconds INTEGER NOT NULL,
                    video_data BLOB NOT NULL,
                    video_mime TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    UNIQUE(run_id,item_id),
                    FOREIGN KEY(run_id) REFERENCES online_test_runs(id) ON DELETE CASCADE,
                    FOREIGN KEY(item_id) REFERENCES assignment_items(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_test_runs_assignment ON online_test_runs(assignment_id);
            """)

    def register_user(self, username: str, password: str, full_name: str, role: str, grade: int | None = None, class_letter: str | None = None) -> int:
        if role not in {"student", "teacher"}:
            raise ValueError("Role must be student or teacher")
        with self.connect() as con:
            cur = con.execute(
                "INSERT INTO users(username,password_hash,full_name,role,grade,class_letter,created_at) VALUES(?,?,?,?,?,?,?)",
                (username.strip(), hash_password(password), full_name.strip(), role, grade, (class_letter or "").strip().upper() or None, utc_now()),
            )
            return int(cur.lastrowid)

    def register_student_with_class(self, username: str, password: str, full_name: str, join_code: str) -> tuple[int, str]:
        code = join_code.strip().upper()
        if not code:
            raise ValueError("Сынып кодын енгізу міндетті")
        with self.connect() as con:
            cls = con.execute("SELECT * FROM classes WHERE join_code=?", (code,)).fetchone()
            if not cls:
                raise ValueError("Сынып коды дұрыс емес")
            match = re.match(r"^\s*(\d{1,2})\s*[- ]?\s*([А-ЯӘҒҚҢӨҰҮҺA-Z])?", str(cls["name"]).upper())
            grade = int(match.group(1)) if match else None
            letter = match.group(2) if match and match.group(2) else None
            if letter:
                latin_map = {"A":"А","B":"Б","V":"В","G":"Г","D":"Д","E":"Е","K":"К","M":"М"}
                letter = latin_map.get(letter, letter)
            cur = con.execute(
                "INSERT INTO users(username,password_hash,full_name,role,grade,class_letter,created_at) VALUES(?,?,?,?,?,?,?)",
                (username.strip(), hash_password(password), full_name.strip(), "student", grade, letter, utc_now()),
            )
            uid = int(cur.lastrowid)
            con.execute("INSERT INTO class_members(class_id,student_id,joined_at) VALUES(?,?,?)", (cls["id"], uid, utc_now()))
            return uid, str(cls["name"])

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        with self.connect() as con:
            row = con.execute("SELECT * FROM users WHERE username=?", (username.strip(),)).fetchone()
        if row and verify_password(password, row["password_hash"]):
            return dict(row)
        return None

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        with self.connect() as con:
            row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            return dict(row) if row else None

    def update_grade(self, user_id: int, grade: int) -> None:
        with self.connect() as con:
            con.execute("UPDATE users SET grade=? WHERE id=?", (grade, user_id))

    def update_class_profile(self, user_id: int, grade: int, class_letter: str | None) -> None:
        letter = (class_letter or "").strip().upper() or None
        with self.connect() as con:
            con.execute("UPDATE users SET grade=?, class_letter=? WHERE id=?", (grade, letter, user_id))

    def class_by_code(self, join_code: str) -> dict[str, Any] | None:
        with self.connect() as con:
            row = con.execute("SELECT * FROM classes WHERE join_code=?", (join_code.strip().upper(),)).fetchone()
        return dict(row) if row else None

    def create_class(self, teacher_id: int, name: str) -> dict[str, Any]:
        code = secrets.token_hex(3).upper()
        with self.connect() as con:
            cur = con.execute(
                "INSERT INTO classes(teacher_id,name,join_code,created_at) VALUES(?,?,?,?)",
                (teacher_id, name.strip(), code, utc_now()),
            )
            cid = int(cur.lastrowid)
        return {"id": cid, "name": name.strip(), "join_code": code}

    def teacher_classes(self, teacher_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute("SELECT * FROM classes WHERE teacher_id=? ORDER BY id DESC", (teacher_id,)).fetchall()
        return [dict(r) for r in rows]

    def join_class(self, student_id: int, join_code: str) -> str:
        with self.connect() as con:
            cls = con.execute("SELECT * FROM classes WHERE join_code=?", (join_code.strip().upper(),)).fetchone()
            if not cls:
                raise ValueError("Сынып коды табылмады")
            con.execute(
                "INSERT OR IGNORE INTO class_members(class_id,student_id,joined_at) VALUES(?,?,?)",
                (cls["id"], student_id, utc_now()),
            )
            # Keep the student's profile synchronized with teacher-created class names such as 9А / 9Ә / 10Б.
            match = re.match(r"^\s*(\d{1,2})\s*[- ]?\s*([А-ЯӘҒҚҢӨҰҮҺA-Z])?", str(cls["name"]).upper())
            if match:
                grade = int(match.group(1))
                letter = match.group(2) or None
                if letter:
                    latin_map = {"A": "А", "B": "Б", "V": "В", "G": "Г", "D": "Д", "E": "Е", "K": "К", "M": "М"}
                    letter = latin_map.get(letter, letter)
                con.execute("UPDATE users SET grade=?, class_letter=? WHERE id=?", (grade, letter, student_id))
        return str(cls["name"])

    def student_classes(self, student_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """SELECT c.* FROM classes c JOIN class_members m ON m.class_id=c.id
                   WHERE m.student_id=? ORDER BY c.name""",
                (student_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def class_students(self, class_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """SELECT u.* FROM users u JOIN class_members m ON m.student_id=u.id
                   WHERE m.class_id=? ORDER BY u.full_name""",
                (class_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def ensure_topics(self, student_id: int, grade: int, topics: Iterable[str]) -> None:
        with self.connect() as con:
            for topic in topics:
                con.execute(
                    """INSERT OR IGNORE INTO mastery(student_id,grade,topic,score,confidence,attempts,correct)
                       VALUES(?,?,?,?,?,?,?)""",
                    (student_id, grade, topic, 50.0, 20.0, 0, 0),
                )

    def get_mastery(self, student_id: int, grade: int | None = None) -> list[dict[str, Any]]:
        with self.connect() as con:
            if grade is None:
                rows = con.execute(
                    "SELECT * FROM mastery WHERE student_id=? ORDER BY score ASC", (student_id,)
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM mastery WHERE student_id=? AND grade=? ORDER BY score ASC",
                    (student_id, grade),
                ).fetchall()
        return [dict(r) for r in rows]

    def update_mastery(self, student_id: int, grade: int, topic: str, correct: bool, weight: float = 0.30) -> dict[str, Any]:
        self.ensure_topics(student_id, grade, [topic])
        with self.connect() as con:
            row = con.execute(
                "SELECT * FROM mastery WHERE student_id=? AND grade=? AND topic=?",
                (student_id, grade, topic),
            ).fetchone()
            attempts = int(row["attempts"]) + 1
            correct_count = int(row["correct"]) + (1 if correct else 0)
            observed = 100.0 if correct else 0.0
            score = float(row["score"]) * (1.0 - weight) + observed * weight
            confidence = min(100.0, 20.0 + attempts * 8.0)
            con.execute(
                """UPDATE mastery SET score=?,confidence=?,attempts=?,correct=?,last_practiced=?
                   WHERE student_id=? AND grade=? AND topic=?""",
                (round(score, 2), confidence, attempts, correct_count, utc_now(), student_id, grade, topic),
            )
        return {"topic": topic, "score": round(score, 2), "confidence": confidence, "attempts": attempts}

    def set_mastery(self, student_id: int, grade: int, topic: str, score: float, attempts: int, correct: int) -> None:
        score = max(0.0, min(100.0, float(score)))
        confidence = min(100.0, 20.0 + attempts * 8.0)
        with self.connect() as con:
            con.execute(
                """INSERT INTO mastery(student_id,grade,topic,score,confidence,attempts,correct,last_practiced)
                   VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(student_id,grade,topic) DO UPDATE SET
                     score=excluded.score, confidence=excluded.confidence, attempts=excluded.attempts,
                     correct=excluded.correct, last_practiced=excluded.last_practiced""",
                (student_id, grade, topic, score, confidence, attempts, correct, utc_now()),
            )

    def log_attempt(self, **kwargs: Any) -> int:
        fields = [
            "student_id","activity_type","topic","difficulty","question_id","question_text",
            "student_answer","correct_answer","is_correct","confidence","score","error_type","feedback"
        ]
        vals = [kwargs.get(f) for f in fields]
        with self.connect() as con:
            cur = con.execute(
                f"INSERT INTO attempts({','.join(fields)},created_at) VALUES({','.join(['?']*len(fields))},?)",
                vals + [utc_now()],
            )
            return int(cur.lastrowid)

    def attempts(self, student_id: int, limit: int = 200) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT * FROM attempts WHERE student_id=? ORDER BY id DESC LIMIT ?",
                (student_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def save_diagnostic(self, student_id: int, grade: int, total: int, correct: int, topic_stats: dict[str, Any],
                        focus_topic: str | None = None, phase: str | None = None) -> int:
        percent = round((correct / total) * 100, 1) if total else 0.0
        with self.connect() as con:
            cur = con.execute(
                """INSERT INTO diagnostic_runs(student_id,grade,total,correct,percent,topic_json,created_at,focus_topic,phase)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (student_id, grade, total, correct, percent, json.dumps(topic_stats, ensure_ascii=False), utc_now(), focus_topic, phase),
            )
            return int(cur.lastrowid)

    def diagnostic_history(self, student_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT * FROM diagnostic_runs WHERE student_id=? ORDER BY id DESC", (student_id,)
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["topic_json"] = json.loads(d["topic_json"])
            out.append(d)
        return out

    def record_mistake(self, student_id: int, topic: str, mistake_type: str, description: str) -> None:
        with self.connect() as con:
            row = con.execute(
                """SELECT * FROM mistakes WHERE student_id=? AND topic=? AND mistake_type=? AND resolved=0""",
                (student_id, topic, mistake_type),
            ).fetchone()
            if row:
                con.execute(
                    "UPDATE mistakes SET frequency=frequency+1, description=?, last_seen=? WHERE id=?",
                    (description, utc_now(), row["id"]),
                )
            else:
                con.execute(
                    """INSERT INTO mistakes(student_id,topic,mistake_type,description,frequency,resolved,last_seen)
                       VALUES(?,?,?,?,1,0,?)""",
                    (student_id, topic, mistake_type, description, utc_now()),
                )

    def get_mistakes(self, student_id: int, unresolved_only: bool = True) -> list[dict[str, Any]]:
        q = "SELECT * FROM mistakes WHERE student_id=?"
        if unresolved_only:
            q += " AND resolved=0"
        q += " ORDER BY frequency DESC, id DESC"
        with self.connect() as con:
            rows = con.execute(q, (student_id,)).fetchall()
        return [dict(r) for r in rows]

    def resolve_mistake(self, mistake_id: int, student_id: int, *, teacher_override: bool = False) -> bool:
        with self.connect() as con:
            mistake = con.execute("SELECT * FROM mistakes WHERE id=? AND student_id=? AND resolved=0", (mistake_id, student_id)).fetchone()
            if not mistake:
                return False
            if not teacher_override:
                passed = con.execute(
                    """SELECT 1 FROM attempts WHERE student_id=? AND activity_type='adaptive'
                       AND topic=? AND is_correct=1 AND created_at>=? ORDER BY id DESC LIMIT 1""",
                    (student_id, mistake["topic"], mistake["last_seen"]),
                ).fetchone()
                if not passed:
                    return False
            con.execute("UPDATE mistakes SET resolved=1 WHERE id=? AND student_id=?", (mistake_id, student_id))
            return True

    def get_review_state(self, student_id: int, topic: str) -> dict[str, Any] | None:
        with self.connect() as con:
            row = con.execute("SELECT * FROM review_state WHERE student_id=? AND topic=?", (student_id, topic)).fetchone()
        return dict(row) if row else None

    def upsert_review_state(self, student_id: int, topic: str, state: dict[str, Any]) -> None:
        with self.connect() as con:
            con.execute(
                """INSERT INTO review_state(student_id,topic,easiness,interval_days,repetition_count,next_review,last_quality,last_reviewed)
                   VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(student_id,topic) DO UPDATE SET
                     easiness=excluded.easiness, interval_days=excluded.interval_days,
                     repetition_count=excluded.repetition_count, next_review=excluded.next_review,
                     last_quality=excluded.last_quality, last_reviewed=excluded.last_reviewed""",
                (
                    student_id, topic, state["easiness"], state["interval_days"], state["repetition_count"],
                    state["next_review"], state["last_quality"], state["last_reviewed"],
                ),
            )

    def all_review_states(self, student_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute("SELECT * FROM review_state WHERE student_id=?", (student_id,)).fetchall()
        return [dict(r) for r in rows]

    def add_chat(self, student_id: int, role: str, content: str, topic: str | None = None) -> None:
        with self.connect() as con:
            con.execute(
                "INSERT INTO chats(student_id,role,content,topic,created_at) VALUES(?,?,?,?,?)",
                (student_id, role, content, topic, utc_now()),
            )

    def chat_history(self, student_id: int, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT * FROM chats WHERE student_id=? ORDER BY id DESC LIMIT ?", (student_id, limit)
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def clear_chat(self, student_id: int) -> None:
        with self.connect() as con:
            con.execute("DELETE FROM chats WHERE student_id=?", (student_id,))

    # Unified multimodal assistant persistence. Every method verifies ownership;
    # callers cannot access another user's conversation by changing an id.
    def create_conversation(self, user_id: int, role: str, title: str = "Жаңа чат") -> int:
        if role not in {"teacher", "student"}:
            raise ValueError("Қолжетімсіз рөл")
        stamp = utc_now()
        with self.connect() as con:
            user = con.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
            if not user or user["role"] != role:
                raise PermissionError("Бұл әрекетке рұқсат жоқ")
            cur = con.execute(
                "INSERT INTO conversations(user_id,role,title,created_at,updated_at) VALUES(?,?,?,?,?)",
                (user_id, role, (title or "Жаңа чат").strip()[:120], stamp, stamp),
            )
            return int(cur.lastrowid)

    def conversations(self, user_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT * FROM conversations WHERE user_id=? ORDER BY updated_at DESC, id DESC", (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def conversation(self, conversation_id: int, user_id: int) -> dict[str, Any] | None:
        with self.connect() as con:
            row = con.execute(
                "SELECT * FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id)
            ).fetchone()
        return dict(row) if row else None

    def rename_conversation(self, conversation_id: int, user_id: int, title: str) -> None:
        clean = title.strip()[:120]
        if not clean:
            raise ValueError("Чат атауы бос болмауы керек")
        with self.connect() as con:
            cur = con.execute(
                "UPDATE conversations SET title=?,updated_at=? WHERE id=? AND user_id=?",
                (clean, utc_now(), conversation_id, user_id),
            )
            if cur.rowcount != 1:
                raise PermissionError("Бұл чатқа рұқсат жоқ")

    def delete_conversation(self, conversation_id: int, user_id: int) -> None:
        with self.connect() as con:
            cur = con.execute("DELETE FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id))
            if cur.rowcount != 1:
                raise PermissionError("Бұл чатқа рұқсат жоқ")

    def add_message(self, conversation_id: int, user_id: int, sender: str, text: str, status: str = "completed") -> int:
        if sender not in {"user", "assistant", "system"}:
            raise ValueError("Хабарлама авторы дұрыс емес")
        with self.connect() as con:
            owned = con.execute("SELECT id,title FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id)).fetchone()
            if not owned:
                raise PermissionError("Бұл чатқа рұқсат жоқ")
            stamp = utc_now()
            cur = con.execute(
                "INSERT INTO messages(conversation_id,sender,text,status,created_at) VALUES(?,?,?,?,?)",
                (conversation_id, sender, text, status, stamp),
            )
            if sender == "user" and owned["title"] == "Жаңа чат":
                title = re.sub(r"\s+", " ", text).strip()[:56] or "Жаңа чат"
                con.execute("UPDATE conversations SET title=?,updated_at=? WHERE id=?", (title, stamp, conversation_id))
            else:
                con.execute("UPDATE conversations SET updated_at=? WHERE id=?", (stamp, conversation_id))
            return int(cur.lastrowid)

    def messages(self, conversation_id: int, user_id: int, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as con:
            owned = con.execute("SELECT id FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id)).fetchone()
            if not owned:
                raise PermissionError("Бұл чатқа рұқсат жоқ")
            rows = con.execute(
                "SELECT * FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?", (conversation_id, limit)
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def add_attachment(self, message_id: int, user_id: int, filename: str, mime_type: str, file_path: str, file_size: int) -> int:
        with self.connect() as con:
            owned = con.execute(
                """SELECT m.id FROM messages m JOIN conversations c ON c.id=m.conversation_id
                   WHERE m.id=? AND c.user_id=?""", (message_id, user_id)
            ).fetchone()
            if not owned:
                raise PermissionError("Бұл файлға рұқсат жоқ")
            cur = con.execute(
                "INSERT INTO attachments(message_id,filename,mime_type,file_path,file_size,created_at) VALUES(?,?,?,?,?,?)",
                (message_id, filename, mime_type, file_path, int(file_size), utc_now()),
            )
            return int(cur.lastrowid)

    def add_generated_file(self, user_id: int, conversation_id: int, filename: str, file_type: str, path: str, metadata: dict[str, Any] | None = None) -> int:
        with self.connect() as con:
            owned = con.execute("SELECT id FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id)).fetchone()
            if not owned:
                raise PermissionError("Бұл чатқа рұқсат жоқ")
            cur = con.execute(
                "INSERT INTO generated_files(filename,type,path,creator,conversation_id,metadata_json,created_at) VALUES(?,?,?,?,?,?,?)",
                (filename, file_type, path, user_id, conversation_id, json.dumps(metadata or {}, ensure_ascii=False), utc_now()),
            )
            return int(cur.lastrowid)

    def generated_files(self, conversation_id: int, user_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """SELECT g.* FROM generated_files g JOIN conversations c ON c.id=g.conversation_id
                   WHERE g.conversation_id=? AND c.user_id=? ORDER BY g.id""", (conversation_id, user_id)
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
            result.append(item)
        return result

    def record_tool_call(self, conversation_id: int, user_id: int, tool_name: str, arguments: dict[str, Any], status: str, duration_ms: int | None = None, result_reference: str | None = None) -> int:
        with self.connect() as con:
            owned = con.execute("SELECT id FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id)).fetchone()
            if not owned:
                raise PermissionError("Бұл чатқа рұқсат жоқ")
            cur = con.execute(
                "INSERT INTO tool_calls(conversation_id,tool_name,arguments_json,status,result_reference,duration_ms,created_at) VALUES(?,?,?,?,?,?,?)",
                (conversation_id, tool_name, json.dumps(arguments, ensure_ascii=False), status, result_reference, duration_ms, utc_now()),
            )
            return int(cur.lastrowid)

    def add_document(self, teacher_id: int, filename: str, title: str, chunks: list[str]) -> int:
        with self.connect() as con:
            cur = con.execute(
                "INSERT INTO documents(teacher_id,filename,title,created_at) VALUES(?,?,?,?)",
                (teacher_id, filename, title, utc_now()),
            )
            did = int(cur.lastrowid)
            for i, chunk in enumerate(chunks):
                con.execute(
                    "INSERT INTO document_chunks(document_id,chunk_index,content) VALUES(?,?,?)",
                    (did, i, chunk),
                )
        return did

    def list_documents(self, teacher_id: int | None = None) -> list[dict[str, Any]]:
        with self.connect() as con:
            if teacher_id is None:
                rows = con.execute("SELECT * FROM documents ORDER BY id DESC").fetchall()
            else:
                rows = con.execute("SELECT * FROM documents WHERE teacher_id=? ORDER BY id DESC", (teacher_id,)).fetchall()
        return [dict(r) for r in rows]

    def delete_document(self, document_id: int, teacher_id: int) -> None:
        with self.connect() as con:
            con.execute("DELETE FROM documents WHERE id=? AND teacher_id=?", (document_id, teacher_id))

    def all_chunks(self) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """SELECT dc.id, dc.content, dc.chunk_index, d.title, d.filename, d.id AS document_id
                   FROM document_chunks dc JOIN documents d ON d.id=dc.document_id"""
            ).fetchall()
        return [dict(r) for r in rows]

    def assign_document_to_classes(self, document_id: int, teacher_id: int, class_ids: list[int]) -> None:
        """Bind a teacher document to owned classes so RAG never leaks across classes."""
        unique_ids = sorted({int(x) for x in class_ids})
        with self.connect() as con:
            doc = con.execute(
                "SELECT id FROM documents WHERE id=? AND teacher_id=?", (document_id, teacher_id)
            ).fetchone()
            if not doc:
                raise ValueError("Материал табылмады немесе сізге тиесілі емес")
            con.execute("DELETE FROM document_classes WHERE document_id=?", (document_id,))
            for class_id in unique_ids:
                owned = con.execute(
                    "SELECT id FROM classes WHERE id=? AND teacher_id=?", (class_id, teacher_id)
                ).fetchone()
                if not owned:
                    raise ValueError("Таңдалған сынып мұғалімге тиесілі емес")
                con.execute(
                    "INSERT OR IGNORE INTO document_classes(document_id,class_id) VALUES(?,?)",
                    (document_id, class_id),
                )

    def document_class_ids(self, document_id: int, teacher_id: int) -> list[int]:
        with self.connect() as con:
            rows = con.execute(
                """SELECT dc.class_id FROM document_classes dc
                   JOIN documents d ON d.id=dc.document_id
                   WHERE dc.document_id=? AND d.teacher_id=? ORDER BY dc.class_id""",
                (document_id, teacher_id),
            ).fetchall()
        return [int(r["class_id"]) for r in rows]

    def accessible_chunks_for_student(self, student_id: int) -> list[dict[str, Any]]:
        """Return only RAG chunks explicitly assigned to classes the student belongs to."""
        with self.connect() as con:
            rows = con.execute(
                """SELECT DISTINCT dc.id, dc.content, dc.chunk_index, d.title, d.filename, d.id AS document_id
                   FROM document_chunks dc
                   JOIN documents d ON d.id=dc.document_id
                   JOIN document_classes dcl ON dcl.document_id=d.id
                   JOIN class_members cm ON cm.class_id=dcl.class_id
                   WHERE cm.student_id=?
                   ORDER BY d.id DESC, dc.chunk_index""",
                (student_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def create_assignment(
        self, teacher_id: int, class_id: int, title: str, topic: str, difficulty: str,
        tasks: list[dict[str, Any]], instructions: str = "", due_at: str | None = None,
    ) -> int:
        if not tasks:
            raise ValueError("Кемінде бір тапсырма қажет")
        if difficulty not in {"A", "B", "C"}:
            raise ValueError("Difficulty A/B/C болуы керек")
        with self.connect() as con:
            owned = con.execute(
                "SELECT id FROM classes WHERE id=? AND teacher_id=?", (class_id, teacher_id)
            ).fetchone()
            if not owned:
                raise ValueError("Бұл сынып сізге тиесілі емес")
            cur = con.execute(
                """INSERT INTO assignments(teacher_id,class_id,title,instructions,topic,difficulty,due_at,status,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (teacher_id, class_id, title.strip(), instructions.strip(), topic, difficulty, due_at, "active", utc_now()),
            )
            aid = int(cur.lastrowid)
            for pos, task in enumerate(tasks, 1):
                con.execute(
                    "INSERT INTO assignment_items(assignment_id,position,task_json) VALUES(?,?,?)",
                    (aid, pos, json.dumps(task, ensure_ascii=False)),
                )
            con.execute(
                "INSERT INTO audit_log(user_id,action,entity_type,entity_id,metadata_json,created_at) VALUES(?,?,?,?,?,?)",
                (teacher_id, "assignment.create", "assignment", str(aid), json.dumps({"class_id": class_id, "count": len(tasks)}, ensure_ascii=False), utc_now()),
            )
        return aid

    def teacher_assignments(self, teacher_id: int, class_id: int | None = None) -> list[dict[str, Any]]:
        q = """SELECT a.*, c.name AS class_name,
               (SELECT COUNT(*) FROM assignment_items i WHERE i.assignment_id=a.id) AS item_count
               FROM assignments a JOIN classes c ON c.id=a.class_id
               WHERE a.teacher_id=?"""
        params: list[Any] = [teacher_id]
        if class_id is not None:
            q += " AND a.class_id=?"
            params.append(class_id)
        q += " ORDER BY a.id DESC"
        with self.connect() as con:
            rows = con.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def student_assignments(self, student_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """SELECT DISTINCT a.*, c.name AS class_name,
                   (SELECT COUNT(*) FROM assignment_items i WHERE i.assignment_id=a.id) AS item_count,
                   (SELECT COUNT(*) FROM assignment_submissions s WHERE s.assignment_id=a.id AND s.student_id=?) AS submitted_count
                   FROM assignments a
                   JOIN classes c ON c.id=a.class_id
                   JOIN class_members cm ON cm.class_id=a.class_id
                   WHERE cm.student_id=? AND a.status='active'
                   ORDER BY a.id DESC""",
                (student_id, student_id),
            ).fetchall()
        return [dict(r) for r in rows]

    def assignment_items(self, assignment_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT * FROM assignment_items WHERE assignment_id=? ORDER BY position", (assignment_id,)
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            d["task"] = json.loads(d.pop("task_json"))
            out.append(d)
        return out

    def assignment_submissions(self, student_id: int, assignment_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT * FROM assignment_submissions WHERE student_id=? AND assignment_id=?",
                (student_id, assignment_id),
            ).fetchall()
        return [dict(r) for r in rows]

    def submit_assignment_item(
        self, student_id: int, assignment_id: int, item_id: int, answer: str,
        is_correct: bool, score: float, feedback: str,
    ) -> None:
        with self.connect() as con:
            allowed = con.execute(
                """SELECT a.id, i.task_json FROM assignments a
                   JOIN class_members cm ON cm.class_id=a.class_id
                   JOIN assignment_items i ON i.assignment_id=a.id
                   WHERE a.id=? AND i.id=? AND cm.student_id=? AND a.status='active'""",
                (assignment_id, item_id, student_id),
            ).fetchone()
            if not allowed:
                raise ValueError("Бұл тапсырма оқушыға қолжетімсіз")
            stamp = utc_now()
            con.execute(
                """INSERT INTO assignment_submission_history(assignment_id,item_id,student_id,student_answer,task_json,is_correct,score,feedback,submitted_at)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (assignment_id, item_id, student_id, answer, allowed["task_json"], int(is_correct), float(score), feedback, stamp),
            )
            con.execute(
                """INSERT INTO assignment_submissions(assignment_id,item_id,student_id,student_answer,is_correct,score,feedback,submitted_at)
                   VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(item_id,student_id) DO UPDATE SET
                     student_answer=excluded.student_answer,is_correct=excluded.is_correct,score=excluded.score,
                     feedback=excluded.feedback,submitted_at=excluded.submitted_at""",
                (assignment_id, item_id, student_id, answer, int(is_correct), float(score), feedback, stamp),
            )

    def save_assignment_work(self, student_id: int, assignment_id: int, image_data: bytes, mime_type: str, ai_feedback: str, score: float) -> None:
        with self.connect() as con:
            allowed = con.execute(
                """SELECT a.id FROM assignments a JOIN class_members cm ON cm.class_id=a.class_id
                   WHERE a.id=? AND cm.student_id=? AND a.status='active'""",
                (assignment_id, student_id),
            ).fetchone()
            if not allowed:
                raise ValueError("Бұл тапсырма оқушыға қолжетімсіз")
            stamp = utc_now()
            con.execute(
                """INSERT INTO assignment_work_history(assignment_id,student_id,image_data,mime_type,ai_feedback,score,submitted_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (assignment_id, student_id, sqlite3.Binary(image_data), mime_type, ai_feedback, float(score), stamp),
            )
            con.execute(
                """INSERT INTO assignment_work_submissions(assignment_id,student_id,image_data,mime_type,ai_feedback,score,submitted_at)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(assignment_id,student_id) DO UPDATE SET image_data=excluded.image_data,mime_type=excluded.mime_type,
                   ai_feedback=excluded.ai_feedback,score=excluded.score,submitted_at=excluded.submitted_at""",
                (assignment_id, student_id, sqlite3.Binary(image_data), mime_type, ai_feedback, float(score), stamp),
            )

    def teacher_assignment_work(self, assignment_id: int, teacher_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """SELECT w.*, u.full_name FROM assignment_work_submissions w
                   JOIN assignments a ON a.id=w.assignment_id
                   JOIN users u ON u.id=w.student_id
                   WHERE w.assignment_id=? AND a.teacher_id=? ORDER BY w.submitted_at DESC""",
                (assignment_id, teacher_id),
            ).fetchall()
        return [dict(r) for r in rows]

    def assignment_stats(self, assignment_id: int, teacher_id: int) -> dict[str, Any]:
        with self.connect() as con:
            own = con.execute(
                "SELECT class_id FROM assignments WHERE id=? AND teacher_id=?", (assignment_id, teacher_id)
            ).fetchone()
            if not own:
                raise ValueError("Тапсырма табылмады")
            total_students = con.execute(
                "SELECT COUNT(*) AS n FROM class_members WHERE class_id=?", (own["class_id"],)
            ).fetchone()["n"]
            item_count = con.execute(
                "SELECT COUNT(*) AS n FROM assignment_items WHERE assignment_id=?", (assignment_id,)
            ).fetchone()["n"]
            row = con.execute(
                """SELECT COUNT(*) AS submitted, AVG(score) AS avg_score,
                   COUNT(DISTINCT student_id) AS students_started
                   FROM assignment_work_submissions WHERE assignment_id=?""",
                (assignment_id,),
            ).fetchone()
        return {
            "total_students": int(total_students or 0),
            "item_count": int(item_count or 0),
            "submitted": int(row["submitted"] or 0),
            "students_started": int(row["students_started"] or 0),
            "avg_score": float(row["avg_score"] or 0.0),
        }

    def set_assignment_status(self, assignment_id: int, teacher_id: int, status: str) -> None:
        if status not in {"active", "closed"}:
            raise ValueError("Status active/closed болуы керек")
        with self.connect() as con:
            con.execute(
                "UPDATE assignments SET status=? WHERE id=? AND teacher_id=?",
                (status, assignment_id, teacher_id),
            )

    def class_student_overview(self, class_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """SELECT u.id, u.full_name, u.username, u.grade, u.class_letter, u.created_at,
                          m.joined_at,
                          (SELECT COUNT(*) FROM attempts a WHERE a.student_id=u.id) AS attempt_count,
                          (SELECT COUNT(DISTINCT assignment_id) FROM assignment_work_history w WHERE w.student_id=u.id) AS class_work_count,
                          (SELECT COUNT(DISTINCT pisa_assignment_id) FROM pisa_assignment_submissions p WHERE p.student_id=u.id) AS pisa_work_count,
                          COALESCE(
                            (SELECT MAX(x.ts) FROM (
                                SELECT MAX(created_at) AS ts FROM attempts WHERE student_id=u.id
                                UNION ALL SELECT MAX(submitted_at) FROM assignment_work_history WHERE student_id=u.id
                                UNION ALL SELECT MAX(submitted_at) FROM pisa_assignment_submissions WHERE student_id=u.id
                            ) x), u.created_at
                          ) AS last_activity
                   FROM users u
                   JOIN class_members m ON m.student_id=u.id
                   WHERE m.class_id=?
                   ORDER BY u.full_name""",
                (class_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def student_activity_attempts(self, student_id: int, limit: int = 500) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """SELECT id, activity_type, topic, difficulty, question_text, student_answer,
                          correct_answer, is_correct, score, feedback, created_at
                   FROM attempts WHERE student_id=? ORDER BY id DESC LIMIT ?""",
                (student_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def student_assignment_history(self, student_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """SELECT h.*, a.title AS assignment_title, a.topic, a.difficulty,
                          i.position, COALESCE(h.task_json, i.task_json) AS task_json, c.name AS class_name
                   FROM assignment_submission_history h
                   JOIN assignments a ON a.id=h.assignment_id
                   JOIN assignment_items i ON i.id=h.item_id
                   JOIN classes c ON c.id=a.class_id
                   WHERE h.student_id=? ORDER BY h.id DESC""",
                (student_id,),
            ).fetchall()
        out=[]
        for r in rows:
            d=dict(r)
            try: d["task"] = json.loads(d.pop("task_json"))
            except Exception: d["task"] = {}
            out.append(d)
        return out

    def student_work_history(self, student_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """SELECT h.*, a.title AS assignment_title, a.topic, c.name AS class_name
                   FROM assignment_work_history h
                   JOIN assignments a ON a.id=h.assignment_id
                   JOIN classes c ON c.id=a.class_id
                   WHERE h.student_id=? ORDER BY h.id DESC""",
                (student_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def create_pisa_assignment(self, teacher_id: int, class_id: int, title: str, topic: str, task: dict[str, Any]) -> int:
        with self.connect() as con:
            owned = con.execute("SELECT id FROM classes WHERE id=? AND teacher_id=?", (class_id, teacher_id)).fetchone()
            if not owned:
                raise ValueError("Бұл сынып сізге тиесілі емес")
            cur = con.execute(
                """INSERT INTO pisa_assignments(teacher_id,class_id,title,topic,task_json,status,created_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (teacher_id, class_id, title.strip(), topic.strip(), json.dumps(task, ensure_ascii=False), "active", utc_now()),
            )
            return int(cur.lastrowid)

    def teacher_pisa_assignments(self, teacher_id: int, class_id: int | None = None) -> list[dict[str, Any]]:
        q = """SELECT p.*, c.name AS class_name,
                      (SELECT COUNT(DISTINCT student_id) FROM pisa_assignment_submissions s WHERE s.pisa_assignment_id=p.id) AS submitted_students
               FROM pisa_assignments p JOIN classes c ON c.id=p.class_id WHERE p.teacher_id=?"""
        params: list[Any] = [teacher_id]
        if class_id is not None:
            q += " AND p.class_id=?"
            params.append(class_id)
        q += " ORDER BY p.id DESC"
        with self.connect() as con:
            rows = con.execute(q, params).fetchall()
        out=[]
        for r in rows:
            d=dict(r)
            try: d["task"] = json.loads(d.pop("task_json"))
            except Exception: d["task"] = {}
            out.append(d)
        return out

    def student_pisa_assignments(self, student_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """SELECT DISTINCT p.*, c.name AS class_name,
                          (SELECT COUNT(*) FROM pisa_assignment_submissions s WHERE s.pisa_assignment_id=p.id AND s.student_id=?) AS response_count
                   FROM pisa_assignments p
                   JOIN classes c ON c.id=p.class_id
                   JOIN class_members cm ON cm.class_id=p.class_id
                   WHERE cm.student_id=? AND p.status='active'
                   ORDER BY p.id DESC""",
                (student_id, student_id),
            ).fetchall()
        out=[]
        for r in rows:
            d=dict(r)
            try: d["task"] = json.loads(d.pop("task_json"))
            except Exception: d["task"] = {}
            out.append(d)
        return out

    def submit_pisa_response(self, pisa_assignment_id: int, student_id: int, question_index: int,
                             question_text: str, student_answer: str, correct_answer: str,
                             is_correct: bool | None, score: float | None, feedback: str) -> None:
        with self.connect() as con:
            allowed = con.execute(
                """SELECT p.id FROM pisa_assignments p
                   JOIN class_members cm ON cm.class_id=p.class_id
                   WHERE p.id=? AND cm.student_id=? AND p.status='active'""",
                (pisa_assignment_id, student_id),
            ).fetchone()
            if not allowed:
                raise ValueError("Бұл PISA тапсырмасы қолжетімсіз")
            con.execute(
                """INSERT INTO pisa_assignment_submissions(
                     pisa_assignment_id,student_id,question_index,question_text,student_answer,
                     correct_answer,is_correct,score,feedback,submitted_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (pisa_assignment_id, student_id, int(question_index), question_text, student_answer,
                 correct_answer, int(is_correct) if is_correct is not None else None,
                 float(score) if score is not None else None, feedback, utc_now()),
            )

    def grade_pisa_response(self, response_id: int, teacher_id: int, correct: bool, feedback: str) -> bool:
        with self.connect() as con:
            response = con.execute(
                """SELECT s.student_id,s.pisa_assignment_id,s.question_index,p.topic,u.grade
                   FROM pisa_assignment_submissions s JOIN pisa_assignments p ON p.id=s.pisa_assignment_id
                   JOIN users u ON u.id=s.student_id
                   WHERE s.id=? AND p.teacher_id=? AND s.is_correct IS NULL""",
                (response_id, teacher_id),
            ).fetchone()
            if not response:
                return False
            changed = con.execute(
                """UPDATE pisa_assignment_submissions SET is_correct=?,score=?,feedback=?
                   WHERE id=? AND EXISTS (SELECT 1 FROM pisa_assignments p
                   WHERE p.id=pisa_assignment_submissions.pisa_assignment_id AND p.teacher_id=?)""",
                (int(correct), 100 if correct else 0, feedback.strip(), response_id, teacher_id),
            )
            con.execute(
                """UPDATE attempts SET is_correct=?,score=?,feedback=? WHERE id=(
                   SELECT id FROM attempts WHERE student_id=? AND activity_type='teacher_pisa'
                   AND question_id=? AND is_correct IS NULL ORDER BY id DESC LIMIT 1)""",
                (int(correct), 100 if correct else 0, feedback.strip(), response["student_id"],
                 f"TPISA-{response['pisa_assignment_id']}-{response['question_index']}"),
            )
        if changed.rowcount == 1:
            self.update_mastery(response["student_id"], int(response["grade"] or 9), response["topic"], correct, weight=0.18)
            return True
        return False

    def grade_personal_pisa_attempt(self, attempt_id: int, teacher_id: int, correct: bool, feedback: str) -> bool:
        with self.connect() as con:
            row = con.execute(
                """SELECT a.student_id,a.topic,u.grade FROM attempts a JOIN users u ON u.id=a.student_id
                   JOIN class_members cm ON cm.student_id=a.student_id JOIN classes c ON c.id=cm.class_id
                   WHERE a.id=? AND a.activity_type='pisa' AND a.is_correct IS NULL AND c.teacher_id=?""",
                (attempt_id, teacher_id),
            ).fetchone()
            if not row:
                return False
            changed = con.execute("UPDATE attempts SET is_correct=?,score=?,feedback=? WHERE id=? AND is_correct IS NULL",
                                  (int(correct), 100 if correct else 0, feedback.strip(), attempt_id))
        if changed.rowcount == 1:
            self.update_mastery(row["student_id"], int(row["grade"] or 9), row["topic"], correct, weight=0.18)
            return True
        return False

    def teacher_pisa_results(self, pisa_assignment_id: int, teacher_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """SELECT s.*, u.full_name FROM pisa_assignment_submissions s
                   JOIN pisa_assignments p ON p.id=s.pisa_assignment_id
                   JOIN users u ON u.id=s.student_id
                   WHERE s.pisa_assignment_id=? AND p.teacher_id=?
                   ORDER BY u.full_name, s.id""",
                (pisa_assignment_id, teacher_id),
            ).fetchall()
        return [dict(r) for r in rows]

    def set_pisa_assignment_status(self, pisa_assignment_id: int, teacher_id: int, status: str) -> None:
        if status not in {"active", "closed"}:
            raise ValueError("Status active/closed болуы керек")
        with self.connect() as con:
            con.execute("UPDATE pisa_assignments SET status=? WHERE id=? AND teacher_id=?", (status, pisa_assignment_id, teacher_id))

    def add_assistant_message(self, user_id: int, role: str, content: str, artifact_type: str | None = None, artifact_name: str | None = None) -> None:
        with self.connect() as con:
            con.execute(
                "INSERT INTO assistant_messages(user_id,role,content,artifact_type,artifact_name,created_at) VALUES(?,?,?,?,?,?)",
                (user_id, role, content, artifact_type, artifact_name, utc_now()),
            )

    def assistant_history(self, user_id: int, limit: int = 60) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT * FROM assistant_messages WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def clear_assistant_history(self, user_id: int) -> None:
        with self.connect() as con:
            con.execute("DELETE FROM assistant_messages WHERE user_id=?", (user_id,))


    def delete_assignment(self, assignment_id: int, teacher_id: int) -> None:
        with self.connect() as con:
            con.execute("DELETE FROM assignments WHERE id=? AND teacher_id=?", (assignment_id, teacher_id))

    def update_assignment_meta(self, assignment_id: int, teacher_id: int, title: str, topic: str, difficulty: str, instructions: str = "") -> None:
        if difficulty not in {"A", "B", "C"}:
            raise ValueError("Деңгей A/B/C болуы керек")
        with self.connect() as con:
            con.execute(
                """UPDATE assignments SET title=?, topic=?, difficulty=?, instructions=?
                   WHERE id=? AND teacher_id=?""",
                (title.strip(), topic.strip(), difficulty, instructions.strip(), assignment_id, teacher_id),
            )

    def update_assignment_item(self, item_id: int, assignment_id: int, teacher_id: int, task: dict[str, Any]) -> None:
        with self.connect() as con:
            own = con.execute(
                "SELECT id FROM assignments WHERE id=? AND teacher_id=?", (assignment_id, teacher_id)
            ).fetchone()
            if not own:
                raise ValueError("Тапсырма табылмады")
            con.execute(
                "UPDATE assignment_items SET task_json=? WHERE id=? AND assignment_id=?",
                (json.dumps(task, ensure_ascii=False), item_id, assignment_id),
            )

    def teacher_student_assignment_latest(self, student_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """SELECT s.*, a.title AS assignment_title, a.topic, a.difficulty,
                          i.position, i.task_json, c.name AS class_name
                   FROM assignment_submissions s
                   JOIN assignments a ON a.id=s.assignment_id
                   JOIN assignment_items i ON i.id=s.item_id
                   JOIN classes c ON c.id=a.class_id
                   WHERE s.student_id=? ORDER BY s.submitted_at DESC""",
                (student_id,),
            ).fetchall()
        out=[]
        for r in rows:
            d=dict(r)
            try: d["task"] = json.loads(d.pop("task_json"))
            except Exception: d["task"] = {}
            out.append(d)
        return out

    def teacher_assignment_responses(self, assignment_id: int, teacher_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """SELECT s.*, u.full_name, i.position, i.task_json
                   FROM assignment_submissions s
                   JOIN assignments a ON a.id=s.assignment_id
                   JOIN users u ON u.id=s.student_id
                   JOIN assignment_items i ON i.id=s.item_id
                   WHERE s.assignment_id=? AND a.teacher_id=?
                   ORDER BY u.full_name, i.position""",
                (assignment_id, teacher_id),
            ).fetchall()
        out=[]
        for r in rows:
            d=dict(r)
            try: d["task"] = json.loads(d.pop("task_json"))
            except Exception: d["task"] = {}
            out.append(d)
        return out

    def student_teacher_pisa_history(self, student_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """SELECT s.*, p.title, p.topic, c.name AS class_name
                   FROM pisa_assignment_submissions s
                   JOIN pisa_assignments p ON p.id=s.pisa_assignment_id
                   JOIN classes c ON c.id=p.class_id
                   WHERE s.student_id=? ORDER BY s.id DESC""",
                (student_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def set_assignment_delivery_mode(self, assignment_id: int, teacher_id: int, mode: str) -> None:
        if mode not in {"notebook", "online_test"}:
            raise ValueError("Тапсырма түрі дұрыс емес")
        with self.connect() as con:
            cur = con.execute("UPDATE assignments SET delivery_mode=? WHERE id=? AND teacher_id=?", (mode, assignment_id, teacher_id))
            if cur.rowcount != 1:
                raise ValueError("Бұл тапсырма сізге тиесілі емес")

    def start_online_test(self, assignment_id: int, student_id: int) -> dict[str, Any]:
        with self.connect() as con:
            assignment = con.execute("""SELECT a.id FROM assignments a JOIN class_members cm ON cm.class_id=a.class_id
                WHERE a.id=? AND cm.student_id=? AND a.status='active' AND a.delivery_mode='online_test'""", (assignment_id,student_id)).fetchone()
            if not assignment:
                raise ValueError("Онлайн тест табылмады немесе оқушыға берілмеген")
            con.execute("INSERT OR IGNORE INTO online_test_runs(assignment_id,student_id,started_at) VALUES(?,?,?)",
                        (assignment_id,student_id,utc_now()))
            row = con.execute("SELECT * FROM online_test_runs WHERE assignment_id=? AND student_id=?",(assignment_id,student_id)).fetchone()
            return dict(row)

    def online_test_report(self, assignment_id: int, student_id: int, teacher_id: int | None = None, *, include_video: bool = False) -> dict[str, Any] | None:
        with self.connect() as con:
            where = " AND a.teacher_id=?" if teacher_id is not None else ""
            params = (assignment_id,student_id,teacher_id) if teacher_id is not None else (assignment_id,student_id)
            run = con.execute("""SELECT r.*,a.title,a.topic,u.full_name FROM online_test_runs r
                JOIN assignments a ON a.id=r.assignment_id JOIN users u ON u.id=r.student_id
                WHERE r.assignment_id=? AND r.student_id=?"""+where,params).fetchone()
            if not run:
                return None
            video_col = "v.video_data" if include_video else "NULL AS video_data"
            answers = con.execute(f"""SELECT v.id,v.item_id,v.answer,v.is_correct,v.duration_seconds,v.video_mime,
                {video_col},v.submitted_at,i.position,i.task_json FROM online_test_answers v
                JOIN assignment_items i ON i.id=v.item_id WHERE v.run_id=? ORDER BY i.position""",(run["id"],)).fetchall()
        result = dict(run)
        result["answers"] = [{**dict(r),"task":json.loads(r["task_json"])} for r in answers]
        return result

    def save_online_test_answer(self, assignment_id: int, student_id: int, item_id: int,
                                answer: str, is_correct: bool, duration_seconds: int,
                                video_data: bytes, video_mime: str) -> None:
        if (not answer.strip() or not video_data or len(video_data)>4_000_000
            or video_mime not in {"video/webm","video/mp4"}
            or not (video_data.startswith(b"\x1a\x45\xdf\xa3") if video_mime == "video/webm" else b"ftyp" in video_data[:16])):
            raise ValueError("Жауап пен камера бейнежазбасы қажет (4 МБ-тан аспасын)")
        with self.connect() as con:
            run = con.execute("""SELECT r.id FROM online_test_runs r JOIN assignments a ON a.id=r.assignment_id
                JOIN class_members cm ON cm.class_id=a.class_id AND cm.student_id=r.student_id
                JOIN assignment_items i ON i.assignment_id=a.id AND i.id=?
                WHERE r.assignment_id=? AND r.student_id=? AND r.finished_at IS NULL AND a.status='active' AND a.delivery_mode='online_test'""",
                (item_id,assignment_id,student_id)).fetchone()
            if not run:
                raise ValueError("Белсенді тест немесе сұрақ табылмады")
            con.execute("""INSERT INTO online_test_answers(run_id,item_id,answer,is_correct,duration_seconds,video_data,video_mime,submitted_at)
                VALUES(?,?,?,?,?,?,?,?)""",(run["id"],item_id,answer.strip(),int(is_correct),max(0,int(duration_seconds)),sqlite3.Binary(video_data),video_mime,utc_now()))

    def finish_online_test(self, assignment_id: int, student_id: int) -> None:
        with self.connect() as con:
            run=con.execute("""SELECT r.id,r.finished_at FROM online_test_runs r JOIN assignments a ON a.id=r.assignment_id
                WHERE r.assignment_id=? AND r.student_id=? AND a.delivery_mode='online_test'""",(assignment_id,student_id)).fetchone()
            if not run or run["finished_at"]:
                raise ValueError("Тест табылмады немесе тапсырылып қойған")
            total=con.execute("SELECT COUNT(*) FROM assignment_items WHERE assignment_id=?",(assignment_id,)).fetchone()[0]
            done=con.execute("SELECT COUNT(*) FROM online_test_answers WHERE run_id=?",(run["id"],)).fetchone()[0]
            if total==0 or done!=total:
                raise ValueError("Барлық сұраққа жауап беріңіз")
            con.execute("UPDATE online_test_runs SET finished_at=? WHERE id=?",(utc_now(),run["id"]))

    def teacher_online_test_reports(self, assignment_id: int, teacher_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows=con.execute("""SELECT r.student_id FROM online_test_runs r JOIN assignments a ON a.id=r.assignment_id
                WHERE r.assignment_id=? AND a.teacher_id=? AND r.finished_at IS NOT NULL ORDER BY r.finished_at DESC""",
                (assignment_id,teacher_id)).fetchall()
        return [report for row in rows if (report:=self.online_test_report(assignment_id,row["student_id"],teacher_id))]

    def student_online_test_reports(self, student_id: int) -> list[dict[str, Any]]:
        with self.connect() as con:
            ids=con.execute("SELECT assignment_id FROM online_test_runs WHERE student_id=? AND finished_at IS NOT NULL ORDER BY finished_at DESC",(student_id,)).fetchall()
        return [report for row in ids if (report:=self.online_test_report(row["assignment_id"],student_id))]
