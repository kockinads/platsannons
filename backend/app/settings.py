# backend/app/settings.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # DB
    database_url: str = "sqlite+aiosqlite:///./app.db"

    # Admin auth för /api/admin endpoints
    admin_token: str = "KOCKIN2025"

    # AF / Jobtech
    af_base_url: str = "https://jobsearch.api.jobtechdev.se/search"
    jobtech_api_key: Optional[str] = None
    af_user_agent: str = "platsannons-aggregator/1.0"

    # App
    debug: bool = False

    class Config:
        env_file = ".env"
        env_prefix = "APP_"

settings = Settings()
