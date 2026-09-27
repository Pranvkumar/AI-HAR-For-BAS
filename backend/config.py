"""
Application configuration — environment-driven settings.
"""
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent

# SQLite keeps the MVP runnable with no external services. Point DATABASE_URL at
# PostgreSQL for a deployment: postgresql+psycopg2://user:pass@host:5432/dbname
DEFAULT_SQLITE_PATH = REPO_ROOT / "storage" / "space_monitoring.db"


class Settings(BaseSettings):
    # App
    APP_NAME: str = "AEGIS AI-HAR Operations Console"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"

    # AI engine
    DEMO_MODE: bool = True
    CONFIDENCE_THRESHOLD: float = 0.70
    FRAME_BUFFER_SIZE: int = 16
    INFERENCE_INTERVAL_MS: int = 1000

    # Security
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS — Vite dev server origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Logging
    LOG_LEVEL: str = "INFO"

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

# Ensure the SQLite parent directory exists before the engine connects.
if settings.is_sqlite:
    DEFAULT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
