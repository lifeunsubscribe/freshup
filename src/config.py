from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
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

    # Proxy Trust Configuration
    # Controls whether to trust X-Forwarded-For headers for client IP extraction
    trust_x_forwarded_for: bool = False  # Secure by default
    # Comma-separated list of trusted proxy IPs/CIDR ranges (e.g., "10.0.0.1,192.168.1.0/24")
    # Empty string = trust NO proxies (fail-secure default, X-Forwarded-For will be ignored)
    trusted_proxies: str = ""

    # Redis Configuration (for distributed rate limiting)
    # Optional: If not set, rate limiter falls back to in-memory storage
    # Format: redis://host:port/db or redis://host:port (defaults to db 0)
    redis_url: str = ""

    # Redis Connection Pool Configuration
    # These settings tune the Redis connection pool for performance and reliability
    # Defaults are conservative; adjust based on load testing and production metrics
    redis_max_connections: int = Field(default=50, gt=0)  # Max connections in pool (redis-py default)
    redis_socket_connect_timeout: float = Field(default=5.0, gt=0)  # Timeout for new connections (seconds)
    redis_socket_timeout: float = Field(default=5.0, gt=0)  # Timeout for socket operations (seconds)
    redis_socket_keepalive: bool = True  # Enable TCP keepalive
    redis_health_check_interval: int = Field(default=30, ge=0)  # Health check interval (seconds, 0=disabled)
    redis_retry_on_timeout: bool = True  # Retry operations that timeout

    # Recipe Scraper Configuration
    # Timeout for HTTP requests when scraping recipe URLs
    scraper_request_timeout: float = Field(default=30.0, gt=0)  # Timeout in seconds (default: 30s)

    # Ollama LLM Configuration
    # URL for connecting to Ollama service (default: host.docker.internal for container-to-host)
    ollama_base_url: str = "http://host.docker.internal:11434"
    # Default model to use for LLM operations (format: model:version)
    ollama_model: str = "llama3.1:8b"
    # Polling interval for checking task status updates (seconds)
    task_poll_interval_seconds: int = Field(default=10, gt=0)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.jwt_secret_key:
        raise ValueError(
            "JWT_SECRET_KEY must be set in environment. "
            "Generate with: python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    return settings
