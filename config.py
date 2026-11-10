import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"

def load_secret_key():
    env_key = os.environ.get("CODEPULSE_SECRET_KEY")
    if env_key:
        return env_key
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    key_file = INSTANCE_DIR / ".secret_key"
    if not key_file.exists():
        key_file.write_text(os.urandom(32).hex(), encoding="utf-8")
    return key_file.read_text(encoding="utf-8").strip()

class Config:
    SECRET_KEY = load_secret_key()
    DATABASE = str(INSTANCE_DIR / "codepulse.sqlite3")
    REPOSITORY_DIR = str(INSTANCE_DIR / "repositories")
    ADMIN_USERNAME = os.environ.get("CODEPULSE_ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("CODEPULSE_ADMIN_PASSWORD", "ChangeThisPassword123!")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Strict"
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8
