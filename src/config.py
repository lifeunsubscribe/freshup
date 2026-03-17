from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


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
    # REQUIRED: Must be set in .env file - no default for security
    # Generate with: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 43200  # 30 days (household use case)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.jwt_secret_key:
        raise ValueError(
            "JWT_SECRET_KEY must be set in environment. "
            "Generate with: python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    return settings
