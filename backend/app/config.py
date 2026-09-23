import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

# Ensure environment variables from .env files are loaded into os.environ
load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Microservice Code Studio"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on", "t", "debug")
        return bool(v)
    
    # AI / LLM Configuration
    GEMINI_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None
    
    # Server configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = [
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    
    # Concurrency and worker queue limit (FR-004)
    MAX_CONCURRENT_SESSIONS: int = Field(default=2, description="Max concurrent Docker sandbox executions")
    
    # Sandbox & Docker Execution
    DOCKER_IMAGE: str = Field(
        default="maven:3.9-eclipse-temurin-21",
        description="Docker base image with pre-cached Maven 3.9 and Java 21 LTS"
    )
    MAVEN_CACHE_DIR: str = Field(
        default=str(Path.home() / ".m2" / "repository"),
        description="Host path to Maven local repository for read-only mount"
    )
    WORKSPACE_DIR: str = Field(
        default=str(Path(__file__).resolve().parent.parent / "workspaces"),
        description="Directory where generated code is synthesized and built"
    )
    
    # Maximum auto-repair iterations (Adaptive Constitution Principle V)
    MAX_REPAIR_ATTEMPTS: int = 5
    
    # Allow offline mock fallback without requiring external API keys
    ALLOW_OFFLINE_MOCK: bool = Field(default=False, description="Allow falling back to offline-mock when no API key is supplied")
    
    # Database (anchored to backend/studio.db by default; future migration target is PostgreSQL)
    DATABASE_URL: str = Field(
        default_factory=lambda: f"sqlite:///{(Path(__file__).resolve().parent.parent / 'studio.db').as_posix()}",
        description="Database connection URL (PostgreSQL in production or SQLite for local development)"
    )

settings = Settings()

# Ensure workspace directory exists
os.makedirs(settings.WORKSPACE_DIR, exist_ok=True)

