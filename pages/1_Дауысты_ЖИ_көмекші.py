import streamlit as st

from auth_session import restore_user
from core.database import Database
from voice_assistant import render_voice_assistant

st.set_page_config(page_title="Дауысты ЖИ көмекші", page_icon="🎙️", layout="wide")
st.sidebar.page_link("app.py", label="AI Physics KZ · Басты бет", icon="⚛️")
user = st.session_state.get("user") or restore_user(Database())
if not user:
    st.warning("Алдымен негізгі бетте жүйеге кіріңіз.")
    st.page_link("app.py", label="Кіру бетіне қайту")
    st.stop()
render_voice_assistant(user)
