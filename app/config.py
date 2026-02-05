from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    All sensitive values MUST be set in .env file - no defaults provided.
    """

    # Database configuration (separate credentials for security)
    database_host: str
    database_port: int = 5432
    database_name: str
    database_user: str
    database_password: str

    # Security keys (REQUIRED - no defaults)
    secret_key: str
    encryption_key: str

    # CORS configuration
    cors_origins: str = "http://localhost:3000,http://localhost:8080"

    # JWT configuration
    access_token_expire_minutes: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def database_url(self) -> str:
        """Construct database URL from separate credentials."""
        return f"postgresql://{self.database_user}:{self.database_password}@{self.database_host}:{self.database_port}/{self.database_name}"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache()
def get_settings():
    """Get cached settings instance."""
    try:
        return Settings()
    except Exception as e:
        print("\n" + "="*70)
        print("ERROR: Failed to load configuration!")
        print("="*70)
        print("\nMissing or invalid environment variables.")
        print("\nPlease create a .env file with the following required variables:")
        print("  - DATABASE_HOST")
        print("  - DATABASE_PORT (optional, defaults to 5432)")
        print("  - DATABASE_NAME")
        print("  - DATABASE_USER")
        print("  - DATABASE_PASSWORD")
        print("  - SECRET_KEY (for JWT signing)")
        print("  - ENCRYPTION_KEY (for message encryption)")
        print("  - CORS_ORIGINS (optional, defaults to localhost)")
        print("\nSee .env.example for a template.")
        print("="*70)
        raise
