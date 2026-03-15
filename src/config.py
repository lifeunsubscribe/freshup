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


@lru_cache
def get_settings() -> Settings:
    return Settings()
