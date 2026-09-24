"""Restore signed-in users across browser refreshes using revocable database sessions."""
from __future__ import annotations

import json

import streamlit as st

from core.database import Database

COOKIE_NAME = "aifiz_session"
COOKIE_AGE_SECONDS = 7 * 24 * 60 * 60


def restore_user(db: Database) -> dict | None:
    """Validate the browser's cookie on each new Streamlit connection."""
    if st.session_state.get("user"):
        return st.session_state["user"]
    token = st.context.cookies.get(COOKIE_NAME, "")
    user = db.user_from_auth_session(token)
    if user:
        st.session_state["user"] = user
        st.session_state["auth_token"] = token
    return user


def _write_cookie(token: str, max_age: int) -> None:
    # The token is an opaque random value. Secure is used on the HTTPS production site.
    value = json.dumps(f"{COOKIE_NAME}={token}; Path=/; Max-Age={max_age}; SameSite=Lax")
    st.html(
        f"<script>document.cookie={value}+(location.protocol==='https:'?'; Secure':'');"
        "window.location.reload();</script>",
        unsafe_allow_javascript=True,
    )


def sign_in(db: Database, user: dict) -> None:
    token = db.create_auth_session(int(user["id"]))
    st.session_state["user"] = user
    st.session_state["auth_token"] = token
    _write_cookie(token, COOKIE_AGE_SECONDS)


def sign_out(db: Database) -> None:
    token = st.session_state.get("auth_token") or st.context.cookies.get(COOKIE_NAME, "")
    db.revoke_auth_session(token)
    st.session_state["user"] = None
    st.session_state["auth_token"] = None
    st.session_state["current_task"] = None
    _write_cookie("", 0)
