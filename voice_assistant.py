"""Browser microphone and animated 3D voice assistant for the Streamlit site."""
from __future__ import annotations

import base64
import os
from html import escape

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

from config import DEFAULT_MODEL


def _avatar(history: list[dict[str, str]], voice: bytes | None = None) -> None:
    # CSS 3D avatar works even when third-party script CDNs are unavailable.
    audio = ("data:audio/mpeg;base64," + base64.b64encode(voice).decode()) if voice else ""
    messages = "".join(
        f'<article class="message {"student" if item["role"] == "student" else "ai"}"><small>{"СІЗ" if item["role"] == "student" else "✦ SANAI"}</small><p>{escape(item["text"])}</p></article>'
        for item in history[-12:]
    ) or '<article class="message ai"><small>✦ SANAI</small><p>Сәлем! Физика туралы сұрағыңызды қойыңыз.</p></article>'
    components.html(f"""<!doctype html><html lang="kk"><meta charset="utf-8">
<style>
*{{box-sizing:border-box}}html,body{{margin:0;background:#09172c;color:white;font:16px sans-serif}}
#stage{{position:relative;height:560px;overflow:hidden;border-radius:18px;background:linear-gradient(165deg,#191326,#101620 85%);perspective:800px}}
#halo{{position:absolute;left:50%;top:47%;width:270px;height:340px;transform:translate(-50%,-50%);border:2px solid #6ceaff44;border-radius:50%;box-shadow:0 0 55px #66dfff55}}
#person{{position:absolute;left:50%;top:52%;width:210px;height:310px;transform:translate(-50%,-50%) rotateY(-8deg);transform-style:preserve-3d;animation:idle 4s ease-in-out infinite}}
#hair-back{{position:absolute;left:47px;top:17px;width:120px;height:155px;border-radius:60px 60px 45px 45px;background:linear-gradient(90deg,#151b2c,#3a3045 50%,#141827);box-shadow:10px 8px 16px #0007}}
#neck{{position:absolute;left:88px;top:131px;width:37px;height:45px;background:#c88769}}
#face{{position:absolute;left:59px;top:32px;width:96px;height:118px;border-radius:47% 47% 43% 43%;background:linear-gradient(100deg,#a86652,#efbe94 45%,#d3926d 90%);box-shadow:inset -11px -4px 13px #884a3966,4px 5px 16px #0006;transform:translateZ(24px)}}
#fringe{{position:absolute;left:54px;top:18px;width:106px;height:56px;background:linear-gradient(115deg,#171726,#42374b,#161625);border-radius:65% 65% 22% 20%;transform:translateZ(30px)}}
.eye{{position:absolute;top:92px;width:11px;height:7px;border-radius:50%;background:#202638;transform:translateZ(40px)}}#eye1{{left:83px}}#eye2{{left:124px}}
#mouth{{position:absolute;left:101px;top:126px;width:19px;height:4px;border-radius:50%;background:#913f4a;transform:translateZ(40px)}}
#torso{{position:absolute;top:170px;left:32px;width:150px;height:135px;background:linear-gradient(105deg,#121219,#26222e 42%,#0b1018);clip-path:polygon(18% 0,82% 0,100% 100%,0 100%);border-radius:27px 27px 10px 10px;box-shadow:0 8px 25px #0008;transform:translateZ(8px)}}
#shirt{{position:absolute;top:175px;left:88px;width:38px;height:105px;background:linear-gradient(90deg,#101017,#171824);clip-path:polygon(50% 0,100% 20%,65% 100%,35% 100%,0 20%);transform:translateZ(12px)}}
#arm1,#arm2{{position:absolute;top:172px;width:31px;height:111px;border-radius:22px;background:linear-gradient(90deg,#a86354,#e9b18b);box-shadow:0 5px 12px #0005}}#arm1{{left:18px;transform:rotate(15deg)}}#arm2{{right:16px;transform:rotate(-15deg)}}
#atom{{position:absolute;top:224px;left:124px;color:#88e3e4;font-size:30px;transform:translateZ(25px)}}
#stage.talk #mouth{{animation:talk .22s linear infinite}}#stage.talk #person{{animation:speaking .45s ease-in-out infinite}}
@keyframes idle{{50%{{transform:translate(-50%,-51%) rotateY(8deg) rotateZ(1deg)}}}}@keyframes speaking{{50%{{transform:translate(-50%,-51%) rotateY(5deg)}}}}@keyframes talk{{50%{{height:12px;border-radius:50%}}}}
#speak{{background:#1769ff;color:white;border:0;border-radius:10px;padding:12px 20px;cursor:pointer;margin:12px 0;font-size:16px}}#speak:disabled{{opacity:.5;cursor:default}}
.scene{{display:grid;grid-template-columns:minmax(0,1fr) minmax(270px,32%);gap:12px;height:560px}}
.dialogue{{border-radius:18px;background:#111221;border:1px solid #39384a;display:flex;flex-direction:column;overflow:hidden}}
.dialogue h3{{margin:0;padding:20px 22px;border-bottom:1px solid #39384a;letter-spacing:.16em;font:600 15px Georgia;color:#b7bfcb}}
.thread{{overflow-y:auto;padding:14px 18px;flex:1}}
.message{{background:#162235;border:1px solid #254057;border-radius:18px 18px 18px 6px;margin-bottom:14px;padding:14px 18px;line-height:1.55;word-break:break-word}}
.message.student{{background:#302539;border-color:#523759;margin-left:28px;border-radius:18px 18px 6px 18px}}
.message small{{font-size:12px;letter-spacing:.15em;color:#66dce9;font-weight:bold}}
.message p{{margin:8px 0 0;white-space:pre-wrap}}
@media(max-width:650px){{.scene{{grid-template-columns:1fr;height:auto}}#stage{{height:390px}}.dialogue{{height:240px}}}}
</style><div class="scene"><div id="stage"><div id="halo"></div><div id="person"><div id="hair-back"></div><div id="neck"></div><div id="arm1"></div><div id="arm2"></div><div id="torso"></div><div id="shirt"></div><div id="face"></div><div id="fringe"></div><div id="eye1" class="eye"></div><div id="eye2" class="eye"></div><div id="mouth"></div><div id="atom">⚛</div></div></div><div class="dialogue"><h3>ДИАЛОГ</h3><div class="thread">{messages}</div></div></div>
<div style="text-align:center"><button id="speak" {'disabled' if not voice else ''}>▶ Жауапты тыңдау</button></div>

<script>
const stage=document.querySelector('#stage'),btn=document.querySelector('#speak');
btn.addEventListener('click',()=>{{const sound=new Audio('{audio}');btn.disabled=true;stage.classList.add('talk');
const stop=()=>{{stage.classList.remove('talk');btn.disabled=false}};
sound.onended=stop;sound.onerror=stop;sound.play().catch(stop);}});
</script></html>""", height=635, scrolling=True)


def render_voice_assistant(user: dict) -> None:
    st.title("🎙️ Дауысты ЖИ көмекші")
    st.caption("Физика сұрағын дауыспен немесе мәтінмен қойыңыз. Жауапты тыңдай аласыз.")
    history = st.session_state.setdefault("voice_history", [])
    voice = st.session_state.get("voice_audio")
    _avatar(history, voice)
    mode = st.radio("Сұрақ қою тәсілі", ["🎙️ Дауыс", "⌨️ Мәтін"], horizontal=True, key="voice_mode")
    if mode == "🎙️ Дауыс":
        st.caption("Микрофонды басып, сұрақты айтыңыз. Жазба аяқталған соң «Жауап алу» басыңыз.")
        recording = st.audio_input("Микрофон", key="voice_mic")
        typed = ""
    else:
        recording = None
        typed = st.text_input("Физика сұрағыңызды жазыңыз", key="voice_question")
    if st.button("Жауап алу", type="primary", key="voice_submit"):
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            st.error("Дауысты көмекшіге арналған API кілті орнатылмаған.")
            return
        if not recording and not typed.strip():
            st.warning("Алдымен сұрақ айтыңыз немесе жазыңыз.")
            return
        try:
            client = OpenAI(api_key=api_key, timeout=45)
            question = typed.strip()
            if recording and not question:
                data = recording.getvalue()
                if len(data) > 24 * 1024 * 1024:
                    st.error("Дыбыс файлы тым үлкен. Қысқарақ сұрақ жазыңыз.")
                    return
                with st.spinner("Дауысты мәтінге айналдырып жатырмын…"):
                    transcript = client.audio.transcriptions.create(
                        model="gpt-4o-mini-transcribe", file=("question.wav", data, "audio/wav"),
                        prompt="Қазақ тіліндегі физика пәні бойынша сұрақ.",
                    )
                    question = transcript.text.strip()
            if not question:
                st.warning("Сұрақты ажырата алмадым. Қайта айтып көріңіз.")
                return
            st.caption(f"Сұрақ: {question}")
            with st.spinner("Жауап дайындалуда…"):
                response = client.responses.create(
                    model=DEFAULT_MODEL,
                    instructions="Сен AI Physics KZ жүйесіндегі физика пәнінің көмекшісісің. Қазақша, түсінікті және қысқа жауап бер. Қауіпті экспериментті үйде жасауға нұсқау берме.",
                    input=question,
                )
                answer = response.output_text.strip()
                if not answer:
                    raise ValueError("ЖИ бос жауап қайтарды")
            history.extend([{"role": "student", "text": question}, {"role": "ai", "text": answer}])
            st.session_state["voice_audio"] = None
            try:
                with st.spinner("Дыбыстап жатырмын…"):
                    speech = client.audio.speech.create(model="gpt-4o-mini-tts",voice="nova",input=answer[:3900],response_format="mp3")
                    st.session_state["voice_audio"] = speech.content
            except Exception:
                st.info("Мәтіндік жауап дайын. Дауыстап оқу әзірге қолжетімсіз.")
            st.rerun()
        except Exception as exc:
            st.error(f"Жауап алу мүмкін болмады: {type(exc).__name__}. Кейін қайта көріңіз.")
