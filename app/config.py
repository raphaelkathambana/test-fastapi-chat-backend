from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/chatdb"
    secret_key: str = "CHANGE-THIS-IN-PRODUCTION-USE-A-STRONG-RANDOM-KEY"
    encryption_key: str = "CHANGE-THIS-IN-PRODUCTION-USE-A-STRONG-RANDOM-KEY"
    
    class Config:
        env_file = ".env"
    
    def __post_init__(self):
        """Warn if default keys are being used."""
        if "CHANGE-THIS" in self.secret_key:
            import warnings
            warnings.warn(
                "Using default SECRET_KEY! Set a secure key in .env for production",
                UserWarning
            )
        if "CHANGE-THIS" in self.encryption_key:
            import warnings
            warnings.warn(
                "Using default ENCRYPTION_KEY! Set a secure key in .env for production",
                UserWarning
            )


@lru_cache()
def get_settings():
    return Settings()
