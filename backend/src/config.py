"""Application configuration loaded from environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """Global application settings with .env support."""

    # ViMax configuration
    VIMAX_ROOT: str = "/Users/wangchangbin/ai/ViMax-main"
    WORKING_DIR_ROOT: str = "/Users/wangchangbin/ai/vimax_ru"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///data/vimax_web.db"

    # ComfyUI
    COMFYUI_BASE_URL: str = "http://192.168.3.4:8188"

    # User
    DEFAULT_USERNAME: str = "muze"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    model_config = {"env_prefix": "VIMAX_", "env_file": ".env", "extra": "ignore"}


settings = AppSettings()
