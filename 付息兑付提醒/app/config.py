import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
LOG_DIR = BASE_DIR / "logs"
FILES_DIR = DATA_DIR / "files"

CONFIG_FILE = DATA_DIR / "config.json"
CONTACTS_FILE = DATA_DIR / "contacts.json"
CUSTOMER_DATA_FILE = DATA_DIR / "customer_data.json"
CUSTOMER_SETTINGS_FILE = DATA_DIR / "customer_settings.json"
BOND_CACHE_FILE = DATA_DIR / "bond_data_cache.csv"
DEFAULT_SMTP_HOST = os.getenv("SMTP_HOST", "smtp.163.com")
DEFAULT_SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
DEFAULT_SMTP_ALT_SSL_PORT = int(os.getenv("SMTP_ALT_SSL_PORT", "994"))
DEFAULT_SMTP_STARTTLS_PORT = int(os.getenv("SMTP_STARTTLS_PORT", "587"))
DEFAULT_SMTP_TIMEOUT = int(os.getenv("SMTP_TIMEOUT", "8"))

SCHEDULER_ENABLED = os.getenv("ENABLE_SCHEDULER", "1").lower() not in {"0", "false", "no"}


def ensure_directories():
    for path in [DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, LOG_DIR, FILES_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def relpath(path):
    try:
        return str(Path(path).resolve().relative_to(BASE_DIR))
    except Exception:
        return str(path)
