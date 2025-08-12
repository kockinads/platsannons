from pydantic import BaseSettings

class Settings(BaseSettings):
    af_base_url: str = "https://jobsearch.api.jobtechdev.se/search"
    jobtech_api_key: str = ""  # lägg ev. din nyckel här
    af_user_agent: str = "platsannons-aggregator/1.0"

settings = Settings()
