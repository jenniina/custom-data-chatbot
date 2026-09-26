"""Configuration shared by the Django site and command-line tools."""
import hmac
import os
from pathlib import Path
import tomllib
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if os.getenv("CONTEXT_ME_LOAD_LOCAL_CONFIG", "true").lower() == "true":
    load_dotenv(ROOT / ".env")

def setting(name, default=""):
    if name in os.environ:
        return os.environ[name]
    # Migration compatibility; no Streamlit package is needed.
    legacy = ROOT / ".streamlit" / "secrets.toml"
    if os.getenv("CONTEXT_ME_LOAD_LOCAL_CONFIG", "true").lower() == "true" and legacy.exists():
        with legacy.open("rb") as handle:
            return str(tomllib.load(handle).get(name, default))
    return default

def role_for(password, admin):
    return "admin" if admin and hmac.compare_digest(password.encode(), admin.encode()) else None

def is_hosted():
    return bool(os.getenv("K_SERVICE")) or setting("CONTEXT_ME_HOSTED", "false").lower() == "true"
