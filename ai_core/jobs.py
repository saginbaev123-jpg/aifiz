from __future__ import annotations

import json
import secrets
from typing import Any

from core.database import utc_now


class JobStore:
    """Persistent job state suitable for a separate Railway worker process."""

    def __init__(self, db: Any):
        self.db = db

    def create(self, user_id: int, conversation_id: int | None, kind: str, payload: dict[str, Any]) -> str:
        job_id = secrets.token_urlsafe(18)
        stamp = utc_now()
        with self.db.connect() as con:
            con.execute(
                "INSERT INTO jobs(id,user_id,conversation_id,kind,status,progress_text,payload_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (job_id, user_id, conversation_id, kind, "queued", "Кезекке қойылды", json.dumps(payload, ensure_ascii=False), stamp, stamp),
            )
        return job_id

    def update(self, job_id: str, user_id: int, status: str, progress: str, result: dict[str, Any] | None = None, error: str | None = None) -> None:
        if status not in {"queued", "running", "completed", "failed"}:
            raise ValueError("Job status is invalid")
        with self.db.connect() as con:
            cur = con.execute(
                "UPDATE jobs SET status=?,progress_text=?,result_json=?,error_text=?,updated_at=? WHERE id=? AND user_id=?",
                (status, progress, json.dumps(result, ensure_ascii=False) if result else None, error, utc_now(), job_id, user_id),
            )
            if cur.rowcount != 1:
                raise PermissionError("Бұл жұмысқа рұқсат жоқ")

    def get(self, job_id: str, user_id: int) -> dict[str, Any] | None:
        with self.db.connect() as con:
            row = con.execute("SELECT * FROM jobs WHERE id=? AND user_id=?", (job_id, user_id)).fetchone()
        return dict(row) if row else None
