from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/chatdb"
    secret_key: str = "your-secret-key-here-change-in-production"
    encryption_key: str = "your-encryption-key-here-change-in-production"
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
