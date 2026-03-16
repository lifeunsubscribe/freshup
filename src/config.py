from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import secrets


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    environment: str = "local"
    database_url: str = "sqlite:///./data/freshup.db"

    # MinIO / S3
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "freshup"
    minio_use_ssl: bool = False

    # JWT Authentication
    jwt_secret_key: str = secrets.token_urlsafe(32)  # Auto-generate for dev, override in .env for prod
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 43200  # 30 days (household use case)


@lru_cache
def get_settings() -> Settings:
    return Settings()
