from pydantic import BaseModel
import os
from functools import lru_cache
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

class Settings(BaseModel):
    app_name: str = os.getenv("APP_NAME", "PolicyLens API")
    api_prefix: str = os.getenv("API_PREFIX", "/api")
    frontend_origins: list[str] = [
        origin.strip()
        for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]
    environment: str = os.getenv("ENVIRONMENT", "dev")

@lru_cache
def get_settings() -> Settings:
    return Settings()
