"""Browser microphone and animated 3D voice assistant for the Streamlit site."""
from __future__ import annotations

import base64
import os
from html import escape
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

from config import DEFAULT_MODEL

MODEL = Path(__file__).parent / "static" / "model22.glb"


def _avatar(answer: str = "", voice: bytes | None = None) -> None:
    # The model is served by Streamlit's static file handler, not embedded in the page.
    audio = ("data:audio/mpeg;base64," + base64.b64encode(voice).decode()) if voice else ""
    text = escape(answer, quote=True)
    components.html(f"""<!doctype html><html lang="kk"><meta charset="utf-8">
<style>
html,body{{margin:0;background:#09172c;color:white;font:16px sans-serif}}
#stage{{position:relative;height:390px;overflow:hidden;border-radius:18px;background:radial-gradient(ellipse at 50% 35%,#1c4674,#09172c 72%)}}
canvas{{display:block;width:100%;height:100%}}#hint{{position:absolute;bottom:14px;left:0;right:0;text-align:center;color:#cae0f2}}
#speak{{background:#1769ff;color:white;border:0;border-radius:10px;padding:12px 20px;cursor:pointer;margin:12px 0;font-size:16px}}
#speak:disabled{{opacity:.5;cursor:default}}.reply{{line-height:1.65;white-space:pre-wrap;padding:4px 12px 10px}}
</style><div id="stage"><div id="hint">3D көмекші жүктелуде…</div></div>
<div style="text-align:center"><button id="speak" {'disabled' if not voice else ''}>▶ Жауапты тыңдау</button></div>
<div class="reply">{text}</div>
<script type="module">
import * as THREE from 'https://unpkg.com/three@0.160.0/build/three.module.js';
import {{GLTFLoader}} from 'https://unpkg.com/three@0.160.0/examples/jsm/loaders/GLTFLoader.js';
const stage=document.querySelector('#stage'),hint=document.querySelector('#hint');
const renderer=new THREE.WebGLRenderer({{antialias:true,alpha:true}});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setSize(stage.clientWidth,390);stage.prepend(renderer.domElement);
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(38,stage.clientWidth/390,.1,100);
scene.add(new THREE.HemisphereLight(0xffffff,0x316090,2.6));
const key=new THREE.DirectionalLight(0xffffff,3);key.position.set(2,4,5);scene.add(key);
let avatar,clock=new THREE.Clock(),talking=false;
new GLTFLoader().load('/app/static/model22.glb',g=>{{
 avatar=g.scene;avatar.rotation.y=Math.PI;
 const bounds=new THREE.Box3().setFromObject(avatar),size=bounds.getSize(new THREE.Vector3()),center=bounds.getCenter(new THREE.Vector3());
 avatar.position.sub(center);const scale=2.9/Math.max(size.y,.001);avatar.scale.setScalar(scale);
 scene.add(avatar);camera.position.set(0,0,5.5);camera.lookAt(0,0,0);hint.textContent='Сұрағыңызды микрофонға айтыңыз немесе жазыңыз';
}},undefined,()=>{{
 const figure=new THREE.Group();const skin=new THREE.MeshStandardMaterial({{color:0xe9aa82}}),coat=new THREE.MeshStandardMaterial({{color:0x2996dc}}),hair=new THREE.MeshStandardMaterial({{color:0x273243}});
 const part=(geo,mat,x,y,z)=>{{const m=new THREE.Mesh(geo,mat);m.position.set(x,y,z);figure.add(m);return m}};
 part(new THREE.SphereGeometry(.39,24,16),skin,0,.8,0);part(new THREE.SphereGeometry(.42,24,16),hair,0,1.02,-.09);
 part(new THREE.CylinderGeometry(.35,.5,1.4,20),coat,0,-.15,0);
 part(new THREE.CylinderGeometry(.13,.13,1.1,12),coat,-.5,-.12,0).rotation.z=-.28;
 part(new THREE.CylinderGeometry(.13,.13,1.1,12),coat,.5,-.12,0).rotation.z=.28;
 part(new THREE.SphereGeometry(.045),new THREE.MeshStandardMaterial({{color:0x13263b}}),-.14,.83,.34);
 part(new THREE.SphereGeometry(.045),new THREE.MeshStandardMaterial({{color:0x13263b}}),.14,.83,.34);
 figure.rotation.y=.1;avatar=figure;scene.add(figure);camera.position.set(0,0,5.5);hint.textContent='Сұрағыңызды микрофонға айтыңыз немесе жазыңыз';
}});
function frame(){{requestAnimationFrame(frame);const t=clock.getElapsedTime();if(avatar){{avatar.rotation.y=Math.PI+Math.sin(t*(talking?4:0.75))*(talking?.09:.035);avatar.position.y=Math.sin(t*(talking?7:1.8))*(talking?.035:.016);}}renderer.render(scene,camera);}}frame();
const btn=document.querySelector('#speak');btn.addEventListener('click',()=>{{
 const sound=new Audio('{audio}');btn.disabled=true;talking=true;
 sound.onended=sound.onerror=()=>{{talking=false;btn.disabled=false}};
 sound.play().catch(()=>{{talking=false;btn.disabled=false}});
}});
</script></html>""", height=530, scrolling=True)


def render_voice_assistant(user: dict) -> None:
    st.title("🎙️ Дауысты ЖИ көмекші")
    st.caption("Физика сұрағын дауыспен немесе мәтінмен қойыңыз. Жауапты тыңдай аласыз.")
    answer = st.session_state.get("voice_answer", "")
    voice = st.session_state.get("voice_audio")
    _avatar(answer, voice)
    recording = st.audio_input("Сұрағыңызды айтыңыз", key="voice_mic")
    typed = st.text_input("Немесе сұрақты жазыңыз", key="voice_question")
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
            st.session_state["voice_answer"] = answer
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
