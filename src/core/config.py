from typing import Optional
from pydantic_settings import BaseSettings as PydanticBaseConfig


class BaseConfig(PydanticBaseConfig):
    model_config = {
        "env_file": "src/.env",
        "extra": "ignore"  # Ignore extra fields not defined in the model
    }

class AppConfig(BaseConfig):
    secret_key: str = "secret_key"
    default_domain: str = "http://127.0.0.1:8000"
    debug: bool = True

    model_config = {
        "env_prefix": "APP_",
        "env_file": "src/.env",
        "extra": "ignore"
    }

app_config = AppConfig()


class DatabaseConfig(BaseConfig):
    username: str = "postgres"
    password: str = "admin"
    database: str = "url_shortener"
    host: str = "localhost"
    port: int = 5432
    pool_size: int = 10
    max_overflow: int = 5
    echo: bool = (
        True  # True means write sql queries in std.out. Set False in production.
    )

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


database_config = DatabaseConfig()


class RedisCpConfig(BaseConfig):
    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None 
    database: int = 0
    max_connections: int = 10
    decode_responses: bool = True
    

    @property
    def redis_url(self) -> str:
        if self.password is None:
            return f"redis://{self.host}:{self.port}/{self.database}"
        else:
            return f"rediss://{self.password}@{self.host}:{self.port}/{self.database}"

    model_config = {
        "env_prefix": "REDIS_",
        "env_file": "src/.env",
        "extra": "ignore"
    }

redis_config = RedisCpConfig()
