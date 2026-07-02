import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "uploads"
LOG_DIR = BASE_DIR / "logs"

CONFIG_FILE = DATA_DIR / "config.json"
TABLE_CACHE_FILE = DATA_DIR / "manuscript_data_cache.csv"

SCHEDULER_ENABLED = os.getenv("ENABLE_SCHEDULER", "1").lower() not in {"0", "false", "no"}


def ensure_directories():
    for path in [DATA_DIR, UPLOAD_DIR, LOG_DIR]:
        path.mkdir(parents=True, exist_ok=True)
