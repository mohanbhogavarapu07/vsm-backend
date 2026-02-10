"""
Application configuration loaded from environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _str(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _bool(key: str, default: bool = False) -> bool:
    return os.environ.get(key, str(default)).lower() in ("true", "1", "yes")


def _int(key: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


class Config:
    """Flask and app configuration."""

    SECRET_KEY = _str("SECRET_KEY", "change-me-in-production")
    DEBUG = _bool("FLASK_DEBUG", True)
    PORT = _int("PORT", 5000)

    # JWT
    JWT_SECRET_KEY = _str("JWT_SECRET_KEY") or SECRET_KEY
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = _int("JWT_EXPIRATION_HOURS", 24)

    # Supabase
    SUPABASE_URL = _str("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = _str("SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_ANON_KEY = _str("SUPABASE_ANON_KEY")
    SUPABASE_KEY = _str("SUPABASE_SERVICE_ROLE_KEY") or _str("SUPABASE_ANON_KEY")

    # CORS (frontend dev servers: Vite often uses 8080, others use 3000/5173)
    CORS_ORIGINS = [o.strip() for o in _str("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:8080").split(",") if o.strip()]
    if not CORS_ORIGINS:
        CORS_ORIGINS = ["http://localhost:3000", "http://localhost:5173", "http://localhost:8080"]

    @classmethod
    def supabase_configured(cls) -> bool:
        return bool(cls.SUPABASE_URL and cls.SUPABASE_KEY)
