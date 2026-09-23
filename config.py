from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load project-local .env before reading any configuration variables.
# override=False keeps explicitly-set system/server environment variables authoritative.
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE, override=False)

DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = Path(os.getenv("AI_PHYSICS_UPLOAD_DIR", str(BASE_DIR / "uploads")))
GENERATED_DIR = Path(os.getenv("AI_PHYSICS_GENERATED_DIR", str(BASE_DIR / "generated_files")))
DB_PATH = Path(os.getenv("AI_PHYSICS_DB", str(DATA_DIR / "ai_physics_kz.db")))

APP_NAME = "AI Physics KZ"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
APP_MODE = os.getenv("APP_MODE", "local").strip().lower()
ALLOW_USER_API_KEY = os.getenv(
    "ALLOW_USER_API_KEY",
    "true" if APP_MODE == "local" else "false",
).strip().lower() in {"1", "true", "yes", "on"}
DEFAULT_GRADE = 9
SUPPORTED_GRADES = [7, 8, 9, 10, 11]
CLASS_LETTERS = ["А", "Ә", "Б", "В", "Г", "Д", "Е", "Ж", "З", "И", "К", "Л", "М"]

DIAGNOSTIC_QUESTION_COUNT = 12
MIN_MASTERY = 0.0
MAX_MASTERY = 100.0

# Adaptive thresholds
LEVEL_A_MAX = 45.0
LEVEL_B_MAX = 75.0

# Local school deployment settings
PBKDF2_ITERATIONS = 240_000
SESSION_TIMEOUT_MINUTES = 120

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
