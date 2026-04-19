import os


def _env_bool(name, default=False):
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name, default, minimum=None, maximum=None):
    raw_value = os.getenv(name)
    try:
        value = int(raw_value) if raw_value is not None else int(default)
    except (TypeError, ValueError):
        value = int(default)
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


API_KEY = (os.getenv("LLM_API_KEY") or os.getenv("MOONSHOT_API_KEY") or "").strip()
LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or "moonshot").strip() or "moonshot"
LLM_API_BASE_URL = (
    os.getenv("LLM_API_BASE_URL")
    or os.getenv("MOONSHOT_API_BASE_URL")
    or "https://api.moonshot.cn/v1"
).strip()
LLM_MODEL = (os.getenv("LLM_MODEL") or os.getenv("MOONSHOT_MODEL") or "moonshot-v1-8k").strip()
LLM_TIMEOUT = _env_int("LLM_TIMEOUT", _env_int("MOONSHOT_TIMEOUT", 60, minimum=5, maximum=300), minimum=5, maximum=300)

FREECAD_BIN_PATH = os.getenv("FREECAD_BIN_PATH", r"E:\FreeCAD 1.0\bin")
FREECAD_PYTHON_PATH = os.getenv("FREECAD_PYTHON_PATH", os.path.join(FREECAD_BIN_PATH, "python.exe"))

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = _env_int("APP_PORT", 5001, minimum=1, maximum=65535)
MAX_HISTORY_LIMIT = _env_int("MAX_HISTORY_LIMIT", 200, minimum=1, maximum=500)
APP_CORS_ORIGINS = [origin.strip() for origin in os.getenv("APP_CORS_ORIGINS", "").split(",") if origin.strip()]

DEMO_MODE = _env_bool("DEMO_MODE", False)
DEMO_NAME = os.getenv("DEMO_NAME", "AI-CAD Public Demo").strip() or "AI-CAD Public Demo"
DEMO_ACCESS_CODE = os.getenv("DEMO_ACCESS_CODE", "").strip()
DEMO_SHOW_HISTORY = _env_bool("DEMO_SHOW_HISTORY", True)
DEMO_ALLOW_GENERATE = _env_bool("DEMO_ALLOW_GENERATE", True)
DEMO_ALLOW_DELETE = _env_bool("DEMO_ALLOW_DELETE", True)
DEMO_ALLOW_DOWNLOAD = _env_bool("DEMO_ALLOW_DOWNLOAD", True)
DEMO_MAX_INSTRUCTION_LENGTH = _env_int("DEMO_MAX_INSTRUCTION_LENGTH", 240, minimum=20, maximum=4000)
DEMO_RATE_LIMIT_WINDOW_SECONDS = _env_int("DEMO_RATE_LIMIT_WINDOW_SECONDS", 300, minimum=10, maximum=3600)
DEMO_RATE_LIMIT_MAX_REQUESTS = _env_int("DEMO_RATE_LIMIT_MAX_REQUESTS", 6, minimum=1, maximum=120)
DEMO_HISTORY_LIMIT = _env_int("DEMO_HISTORY_LIMIT", MAX_HISTORY_LIMIT, minimum=1, maximum=MAX_HISTORY_LIMIT)
ADMIN_ACCESS_CODE = os.getenv("ADMIN_ACCESS_CODE", "").strip()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(BASE_DIR, "database")
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(DATABASE_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
