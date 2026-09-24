"""Browser microphone and animated 3D voice assistant for the Streamlit site."""
from __future__ import annotations

import base64
import hashlib
import io
import os
import shutil
import wave
from html import escape
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

from config import DEFAULT_MODEL

MODEL_STORAGE = Path(os.environ.get("AI_PHYSICS_STORAGE", "/app/storage")) / "sanai" / "model.glb"
MODEL_PUBLIC = Path(__file__).resolve().parent / "static" / "model.glb"


def _restore_model() -> bool:
    """Restore the user-uploaded model after a container restart."""
    if not MODEL_STORAGE.is_file():
        return MODEL_PUBLIC.is_file()
    if not MODEL_PUBLIC.is_file() or MODEL_PUBLIC.stat().st_size != MODEL_STORAGE.stat().st_size:
        MODEL_PUBLIC.parent.mkdir(parents=True, exist_ok=True)
        temporary = MODEL_PUBLIC.with_suffix(".tmp")
        shutil.copyfile(MODEL_STORAGE, temporary)
        temporary.replace(MODEL_PUBLIC)
    return True


def _model_upload(user: dict) -> None:
    if user.get("role") != "teacher":
        return
    with st.expander("Өзім жасаған 3D кейіпкерді қосу"):
        st.caption("SanAI.zip архивінің ішіндегі static/model.glb файлын таңдаңыз (архивтің өзін емес).")
        uploaded = st.file_uploader("3D модель (.glb)", type=["glb"], key="sanai_model_file")
        if uploaded and st.button("3D кейіпкерді сақтау", key="sanai_model_save"):
            if uploaded.size > 110 * 1024 * 1024:
                st.error("Модель 110 МБ-тан аспауы керек.")
                return
            uploaded.seek(0)
            if uploaded.read(4) != b"glTF":
                st.error("Бұл жарамды GLB файлы емес.")
                return
            uploaded.seek(0)
            MODEL_STORAGE.parent.mkdir(parents=True, exist_ok=True)
            temporary = MODEL_STORAGE.with_suffix(".tmp")
            with temporary.open("wb") as output:
                shutil.copyfileobj(uploaded, output)
            temporary.replace(MODEL_STORAGE)
            _restore_model()
            st.success("Кейіпкер сақталды. Бет қайта ашылғанда 3D модель көрінеді.")
            st.rerun()


def _transcribe_recording(client: OpenAI, recording, engine: str = "GPT") -> str:
    data = recording.getvalue()
    if len(data) < 1000:
        raise ValueError("Дыбыс жазылмады. Микрофонға рұқсат беріп, қайта жазып көріңіз.")
    if len(data) > 24 * 1024 * 1024:
        raise ValueError("Дыбыс файлы тым үлкен. Қысқалау сұрақ айтыңыз.")
    try:
        with wave.open(io.BytesIO(data), "rb") as sound:
            if sound.getnframes() / sound.getframerate() < 0.7:
                raise ValueError("Жазба тым қысқа. Сұрағыңызды толық айтып, содан кейін тоқтатыңыз.")
    except wave.Error:
        pass
    transcript = client.audio.transcriptions.create(
        model="whisper-1" if engine == "Whisper" else "gpt-4o-transcribe",
        file=("question.wav", data, "audio/wav"), language="kk",
        prompt="Ньютон заңдары, электр тогы, Архимед күші, күш, масса, жылдамдық, үдеу.",
    )
    if engine == "GPT" and not transcript.text.strip():
        transcript = client.audio.transcriptions.create(
            model="whisper-1", file=("question.wav", data, "audio/wav"), language="kk",
        )
    return transcript.text.strip()


def _avatar(history: list[dict[str, str]], voice: bytes | None = None, has_model: bool = False) -> None:
    # Show only the uploaded SanAI GLB; never substitute a different character.
    audio = ("data:audio/mpeg;base64," + base64.b64encode(voice).decode()) if voice else ""
    messages = "".join(
        f'<article class="message {"student" if item["role"] == "student" else "ai"}"><small>{"СІЗ" if item["role"] == "student" else "✦ SANAI"}</small><p>{escape(item["text"])}</p></article>'
        for item in history[-12:]
    ) or '<article class="message ai"><small>✦ SANAI</small><p>Сәлем! Физика туралы сұрағыңызды қойыңыз.</p></article>'
    components.html(f"""<!doctype html><html lang="kk"><meta charset="utf-8">
<style>
*{{box-sizing:border-box}}html,body{{margin:0;background:#09172c;color:white;font:16px sans-serif}}
#stage{{position:relative;height:560px;overflow:hidden;border-radius:18px;background:linear-gradient(165deg,#191326,#101620 85%);perspective:800px}}
#stage canvas{{position:absolute;inset:0;display:block}}
#model-status{{position:absolute;bottom:12px;left:12px;color:#bad1df;font-size:13px;z-index:2}}
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
</style><div class="scene"><div id="stage"><div id="model-status"></div></div><div class="dialogue"><h3>ДИАЛОГ</h3><div class="thread">{messages}</div></div></div>
<div style="text-align:center"><button id="speak" {'disabled' if not voice else ''}>▶ Жауапты тыңдау</button></div>

<script>
const btn=document.querySelector('#speak');
btn.addEventListener('click',()=>{{const sound=new Audio('{audio}');btn.disabled=true;window.sanaiTalk=true;
const stop=()=>{{btn.disabled=false;window.sanaiTalk=false}};
sound.onended=stop;sound.onerror=stop;sound.play().catch(stop);}});
</script>
<script type="importmap">{{"imports":{{"three":"https://unpkg.com/three@0.160.0/build/three.module.js"}}}}</script>
<script type="module">
if ({'true' if has_model else 'false'}) {{
 const status=document.querySelector('#model-status');status.textContent='3D кейіпкер жүктелуде…';
 try {{
  const THREE=await import('https://unpkg.com/three@0.160.0/build/three.module.js');
  const {{GLTFLoader}}=await import('https://unpkg.com/three@0.160.0/examples/jsm/loaders/GLTFLoader.js');
  const scene=new THREE.Scene(), camera=new THREE.PerspectiveCamera(38,1,.01,100);
  const renderer=new THREE.WebGLRenderer({{antialias:true,alpha:true}});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;
  const area=document.querySelector('#stage');area.prepend(renderer.domElement);
  scene.add(new THREE.HemisphereLight(0xffffff,0x556380,2.7));
  const light=new THREE.DirectionalLight(0xffffff,2.1);light.position.set(2,5,4);scene.add(light);
  new GLTFLoader().load('/app/static/model.glb', gltf=>{{
   const model=gltf.scene;scene.add(model);
   // Use the framing from the original SanAI viewer: measure again after scaling.
   model.rotation.y=Math.PI;
   model.updateMatrixWorld(true);
   let bounds=new THREE.Box3().setFromObject(model);
   const size=new THREE.Vector3(),center=new THREE.Vector3();bounds.getSize(size);
   if(!Number.isFinite(size.y)||size.y<.001){{status.textContent='3D модель өлшемі оқылмады.';return;}}
   model.scale.setScalar(1.7/size.y);
   model.updateMatrixWorld(true);
   bounds=new THREE.Box3().setFromObject(model);bounds.getSize(size);bounds.getCenter(center);
   model.position.x-=center.x;model.position.z-=center.z;model.position.y-=bounds.min.y;
   model.updateMatrixWorld(true);
   bounds=new THREE.Box3().setFromObject(model);bounds.getSize(size);
   const aspect=area.clientWidth/area.clientHeight;
   const vertical=Math.tan(THREE.MathUtils.degToRad(camera.fov)/2);
   const distance=Math.max(size.y/(2*vertical),size.x/(2*vertical*aspect),size.z/(2*vertical))*1.65;
   camera.position.set(0,size.y*.55,distance);camera.lookAt(0,size.y*.5,0);
   camera.near=.05;camera.far=Math.max(100,distance*20);camera.updateProjectionMatrix();
   area.classList.add('model-ready');status.textContent='';
   const mixer=gltf.animations.length?new THREE.AnimationMixer(model):null;
   if(mixer)mixer.clipAction(gltf.animations[0]).play();
   const clock=new THREE.Clock(), mouths=[];
   model.traverse(obj=>{{if(obj.isMesh && obj.morphTargetDictionary){{
    for(const [name,index] of Object.entries(obj.morphTargetDictionary)){{
     if(/mouthopen|jawopen|viseme_aa/i.test(name))mouths.push([obj,index]);
    }}
   }}}});
   function frame(){{requestAnimationFrame(frame);if(mixer)mixer.update(clock.getDelta());
    for(const [mesh,index] of mouths)mesh.morphTargetInfluences[index]=window.sanaiTalk?Math.abs(Math.sin(performance.now()*.015))*.55:0;
    const width=area.clientWidth,height=area.clientHeight;renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();renderer.render(scene,camera);}}
   frame();
  }}, undefined, ()=>{{status.textContent='3D модель ашылмады. Сұрақ қою жұмыс істейді.';}});
 }}catch(error){{status.textContent='3D бейнесі жүктелмеді. Сұрақ қою жұмыс істейді.';}}
}} else {{document.querySelector('#model-status').textContent='3D кейіпкер жүктелмеген. Мұғалім модельді төмендегі бөлімнен қоса алады.';}}
</script></html>""", height=635, scrolling=True)


def render_voice_assistant(user: dict) -> None:
    st.title("🎙️ Дауысты ЖИ көмекші")
    st.caption("Физика сұрағын дауыспен немесе мәтінмен қойыңыз. Жауапты тыңдай аласыз.")
    history = st.session_state.setdefault("voice_history", [])
    mode = st.radio("Сұрақ қою тәсілі", ["🎙️ Дауыс", "⌨️ Мәтін"], horizontal=True, key="voice_mode")
    if mode == "🎙️ Дауыс":
        st.caption("Төмендегі микрофонға рұқсат беріңіз, жазып тоқтатыңыз. Содан кейін «Дауысты тану» басыңыз.")
        recording = st.audio_input("🎙️ Сұрағыңызды қазақша айтыңыз", sample_rate=16000, key="voice_mic")
        engine = st.selectbox("Қазақша дауысты тану тәсілі", ["GPT", "Whisper"],
                              help="Егер бір тәсіл қазақша сөзді қате таныса, екіншісін таңдап, «Дауысты тану» түймесін қайта басыңыз.")
        if recording:
            data = recording.getvalue()
            fingerprint = hashlib.sha256(data).hexdigest()
            if st.session_state.get("voice_recording_id") != fingerprint:
                st.session_state["voice_recording_id"] = fingerprint
                st.session_state["voice_question_draft"] = ""
            st.audio(data, format="audio/wav")
            if st.button("Дауысты тану", key="voice_transcribe"):
                api_key = os.environ.get("OPENAI_API_KEY", "")
                if not api_key:
                    st.error("Railway Variables ішіндегі OPENAI_API_KEY табылмады.")
                else:
                    try:
                        with st.spinner("Қазақша дауысты танып жатырмын…"):
                            st.session_state["voice_question_draft"] = _transcribe_recording(
                                OpenAI(api_key=api_key, timeout=60), recording, engine
                            )
                        if not st.session_state["voice_question_draft"]:
                            st.warning("Сөйлеу анық естілмеді. Жазбаны тыңдап, қайта айтып көріңіз.")
                    except ValueError as exc:
                        st.error(str(exc))
                    except Exception as exc:
                        status = getattr(exc, "status_code", None)
                        st.error(f"Дауысты тану сәтсіз аяқталды: {type(exc).__name__}"
                                 + (f" (HTTP {status})" if status else "")
                                 + ". Микрофон жазбасын тыңдап көріңіз.")
        typed = st.text_area("Танылған сұрақ (қате болса түзетіңіз)", key="voice_question_draft", height=90)
    else:
        recording = None
        typed = st.text_input("Физика сұрағыңызды жазыңыз", key="voice_question")
    if st.button("Жауап алу", type="primary", key="voice_submit"):
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            st.error("Дауысты көмекшіге арналған API кілті орнатылмаған.")
            return
        if not typed.strip():
            st.warning("Алдымен «Дауысты тану» басыңыз немесе сұрақты мәтінмен жазыңыз.")
            return
        try:
            client = OpenAI(api_key=api_key, timeout=45)
            question = typed.strip()
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
    _avatar(history, st.session_state.get("voice_audio"), _restore_model())
    _model_upload(user)
