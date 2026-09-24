import streamlit as st

from voice_assistant import render_voice_assistant

st.set_page_config(page_title="Дауысты ЖИ көмекші", page_icon="🎙️", layout="wide")
user = st.session_state.get("user")
if not user:
    st.warning("Алдымен негізгі бетте жүйеге кіріңіз.")
    st.page_link("app.py", label="Кіру бетіне қайту")
    st.stop()
render_voice_assistant(user)
