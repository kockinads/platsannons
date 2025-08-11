from pydantic import BaseModel
import os

class Settings(BaseModel):
    database_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg2://app:app@localhost:5432/jobs")
    af_base_url: str = os.getenv("AF_BASE_URL", "https://jobsearch.api.jobtechdev.se")
    af_user_agent: str = os.getenv("AF_USER_AGENT", "platsannons-aggregator/1.0")
    recruiter_keywords: list[str] = [s.strip() for s in os.getenv(
        "RECRUITER_KEYWORDS",
        "bemanning,rekrytering,rekryteringsbyrå,rekryteringsföretag,staffing,consultant,headhunt"
    ).split(",") if s.strip()]
    access_token: str = os.getenv("ACCESS_TOKEN", "")  # tomt = ingen inloggning
    jobtech_api_key: str = os.getenv("JOBTECH_API_KEY", "")

settings = Settings()
