"""Download and reuse the official compact Kazakh Vosk model on Railway."""
from __future__ import annotations

import io
import json
import os
import shutil
import stat
import tempfile
import wave
import zipfile
from functools import lru_cache
from pathlib import Path
from urllib.request import urlopen

MODEL_NAME = "vosk-model-small-kz-0.42"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
STORAGE = Path(os.environ.get("AI_PHYSICS_STORAGE", "/app/storage")) / "vosk"


def _model_path() -> Path:
    existing = os.environ.get("VOSK_KZ_MODEL_PATH", "")
    if existing and Path(existing).is_dir():
        return Path(existing)
    destination = STORAGE / MODEL_NAME
    if destination.is_dir() and (destination / "am").is_dir():
        return destination

    STORAGE.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(STORAGE).free < 210 * 1024 * 1024:
        raise RuntimeError("Vosk моделіне сақтау орны жеткіліксіз")
    with tempfile.TemporaryDirectory(prefix="vosk-kz-", dir=STORAGE) as temporary:
        scratch = Path(temporary)
        archive = scratch / "model.zip"
        downloaded = 0
        with urlopen(MODEL_URL, timeout=45) as response, archive.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                downloaded += len(chunk)
                if downloaded > 130 * 1024 * 1024:
                    raise ValueError("Vosk мұрағаты күтілгеннен үлкен")
                output.write(chunk)

        staged = scratch / MODEL_NAME
        staged.mkdir()
        total = 0
        with zipfile.ZipFile(archive) as bundle:
            for item in bundle.infolist():
                parts = Path(item.filename).parts
                if not parts or parts[0] != MODEL_NAME or ".." in parts or Path(item.filename).is_absolute():
                    raise ValueError("Vosk мұрағатының жолы қате")
                if stat.S_ISLNK((item.external_attr >> 16) & 0xFFFF):
                    raise ValueError("Vosk мұрағатында сілтеме бар")
                relative = Path(*parts[1:]) if len(parts) > 1 else Path()
                target = staged / relative
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                elif len(parts) > 1:
                    total += item.file_size
                    if total > 260 * 1024 * 1024:
                        raise ValueError("Vosk мұрағаты күтілгеннен үлкен")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(item) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
        if not (staged / "am").is_dir():
            raise ValueError("Vosk моделі толық жүктелмеді")
        staged.replace(destination)
    return destination


def _check_memory() -> None:
    """Avoid killing the Streamlit process on very small Railway instances."""
    limit_file = Path("/sys/fs/cgroup/memory.max")
    if limit_file.exists():
        raw = limit_file.read_text().strip()
        if raw.isdecimal() and int(raw) < 800 * 1024 * 1024:
            raise RuntimeError("Vosk үшін жедел жад жеткіліксіз")


@lru_cache(maxsize=1)
def _loaded_model():
    from vosk import Model, SetLogLevel

    _check_memory()
    SetLogLevel(-1)
    return Model(str(_model_path()))


def transcribe(audio: bytes) -> str:
    """Recognize a browser-recorded mono PCM WAV with no network API call."""
    from vosk import KaldiRecognizer

    with wave.open(io.BytesIO(audio), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getcomptype() != "NONE":
            raise ValueError("Микрофон жазбасы 16-bit mono WAV болуы керек")
        rate = wav.getframerate()
        if rate < 8000 or rate > 48000:
            raise ValueError("Микрофон жазбасының жиілігі жарамсыз")
        recognizer = KaldiRecognizer(_loaded_model(), rate)
        phrases = []
        while block := wav.readframes(4000):
            if recognizer.AcceptWaveform(block):
                phrases.append(json.loads(recognizer.Result()).get("text", ""))
        phrases.append(json.loads(recognizer.FinalResult()).get("text", ""))
    return " ".join(part for part in phrases if part).strip()
