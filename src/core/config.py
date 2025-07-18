from typing import Optional
from pydantic_settings import BaseSettings as PydanticBaseConfig
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env variables
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

# Top-level raw environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("APP_SECRET_KEY", "your-secret-key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 4320))

# Mailtrap (could be moved to dedicated config)
MAILTRAP_USERNAME = os.getenv("MAILTRAP_USERNAME")
MAILTRAP_PASSWORD = os.getenv("MAILTRAP_PASSWORD")


class BaseConfig(PydanticBaseConfig):
    model_config = {
        "env_file": "src/.env",
        "extra": "ignore"
    }


class AppConfig(BaseConfig):
    secret_key: str = os.getenv("APP_SECRET_KEY", "secret_key")
    default_domain: str = os.getenv("APP_DEFAULT_DOMAIN", "http://127.0.0.1:8000")
    debug: bool = os.getenv("APP_DEBUG", "false").lower() == "true"

    model_config = {
        "env_prefix": "APP_",
        "env_file": "src/.env",
        "extra": "ignore"
    }


class DatabaseConfig(BaseConfig):
    username: str = os.getenv("DB_USERNAME", "postgres")
    password: str = os.getenv("DB_PASSWORD", "admin")
    database: str = os.getenv("DB_DATABASE", "url_shortener")
    host: str = os.getenv("DB_HOST", "localhost")
    port: int = int(os.getenv("DB_PORT", 5432))
    pool_size: int = int(os.getenv("DB_POOL_SIZE", 10))
    max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", 5))
    echo: bool = os.getenv("DB_ECHO", "true").lower() == "true"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    model_config = {
        "env_prefix": "DB_",
        "env_file": "src/.env",
        "extra": "ignore"
    }


class RedisCpConfig(BaseConfig):
    host: str = os.getenv("REDIS_HOST", "localhost")
    port: int = int(os.getenv("REDIS_PORT", 6379))
    password: Optional[str] = os.getenv("REDIS_PASSWORD")
    database: int = int(os.getenv("REDIS_DATABASE", 0))
    max_connections: int = int(os.getenv("REDIS_MAX_CONNECTIONS", 10))
    decode_responses: bool = os.getenv("REDIS_DECODE_RESPONSES", "true").lower() == "true"

    @property
    def redis_url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.database}"
        return f"rediss://{self.host}:{self.port}/{self.database}"

    model_config = {
        "env_prefix": "REDIS_",
        "env_file": "src/.env",
        "extra": "ignore"
    }




# Initialize configs
app_config = AppConfig()
database_config = DatabaseConfig()
redis_config = RedisCpConfig()
