from contextlib import asynccontextmanager
import asyncio
import logging
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError, DatabaseError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.config import get_settings
from src.db.database import Base, init_engine, get_engine, get_session_factory
from src.routers import auth_router, users_router, substitutions_router, inventory_router, recipes_router, grocery_router, prepared_foods_router, scraper_router, tasks_router, receipts_router
from src.middleware.rate_limit import limiter
from src.services.task_worker import background_task_worker
from src.services.llm.client import OllamaClient

logger = logging.getLogger(__name__)

settings = get_settings()

# Tables that must exist for the app to function (excludes alembic_version)
EXPECTED_TABLES = frozenset(Base.metadata.tables.keys())


def _ensure_schema() -> None:
    """Apply any pending Alembic migrations. Creates tables on a fresh DB."""
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(alembic_cfg, "head")


def _ensure_seed_data() -> None:
    """Ensure minimum seed data exists (stores, test user in local)."""
    from src.db.seed import seed
    seed()


def _get_migration_status() -> dict:
    """Check if current DB is at the Alembic head revision."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from alembic.runtime.migration import MigrationContext

    engine = get_engine()
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    head = script.get_current_head()

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        current = ctx.get_current_revision()

    return {"current_revision": current, "head_revision": head, "is_current": current == head}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_engine(settings.database_url)
    _ensure_schema()
    _ensure_seed_data()

    # Start background task worker for processing async LLM tasks (Phase 2A)
    # Worker polls for pending tasks and processes them using OllamaClient
    worker_task = asyncio.create_task(background_task_worker())

    yield

    # Gracefully shut down background worker on application shutdown
    # Cancel the task and wait for it to complete cleanup
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass  # Expected on clean shutdown


app = FastAPI(
    title="FreshUp",
    description="Privacy-first kitchen management system",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — must be added before rate limiting so OPTIONS preflight isn't rejected
if settings.environment == "local":
    # Allow connections from any device on the home LAN (localhost, 192.168.x.x, freshup.local)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|freshup\.local|homelab\.local)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # TODO: read allowed origins from CORS_ALLOWED_ORIGINS setting for production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Register rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Register routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(substitutions_router)
app.include_router(inventory_router)
app.include_router(recipes_router)
app.include_router(grocery_router)
app.include_router(prepared_foods_router)
app.include_router(scraper_router)
app.include_router(tasks_router)
app.include_router(receipts_router)


@app.get("/health")
async def health_check():
    checks = {
        "status": "healthy",
        "environment": settings.environment,
        "database": "unknown",
        "schema": "unknown",
        "migrations": "unknown",
    }
    issues = []

    # 1. Database connectivity
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except (OperationalError, DatabaseError) as e:
        # OperationalError: Connection failures, server errors, query execution issues
        # DatabaseError: Base class for database-related errors
        checks["database"] = "unreachable"
        issues.append(f"db_connect: {e}")
    except Exception as e:
        # Unexpected errors (e.g., configuration issues, driver problems)
        # Health check should never crash, so catch-all is acceptable here
        logger.warning(f"Unexpected error during database connectivity check: {e}", exc_info=True)
        checks["database"] = "unreachable"
        issues.append(f"db_connect_unexpected: {e}")

    # 2. Schema completeness — are all expected tables present?
    if checks["database"] == "connected":
        try:
            inspector = inspect(engine)
            actual_tables = set(inspector.get_table_names())
            missing = EXPECTED_TABLES - actual_tables
            if missing:
                checks["schema"] = "incomplete"
                issues.append(f"missing_tables: {sorted(missing)}")
            else:
                checks["schema"] = "ok"
        except (OperationalError, DatabaseError) as e:
            # Database errors during schema inspection
            checks["schema"] = "error"
            issues.append(f"schema_check: {e}")
        except Exception as e:
            # Unexpected errors during inspection (e.g., reflection issues)
            logger.warning(f"Unexpected error during schema inspection: {e}", exc_info=True)
            checks["schema"] = "error"
            issues.append(f"schema_check_unexpected: {e}")

    # 3. Migration status — is the DB at the Alembic head?
    if checks["database"] == "connected":
        try:
            migration = _get_migration_status()
            if migration["is_current"]:
                checks["migrations"] = "current"
            else:
                checks["migrations"] = "behind"
                issues.append(
                    f"migration: at {migration['current_revision']}, head is {migration['head_revision']}"
                )
        except (OperationalError, DatabaseError) as e:
            # Database errors during migration status check
            checks["migrations"] = "error"
            issues.append(f"migration_check: {e}")
        except Exception as e:
            # Alembic errors (e.g., missing alembic_version table, config issues)
            logger.warning(f"Unexpected error during migration status check: {e}", exc_info=True)
            checks["migrations"] = "error"
            issues.append(f"migration_check_unexpected: {e}")

    if issues:
        checks["status"] = "degraded"
        checks["issues"] = issues

    return checks


@app.get("/health/ollama")
async def ollama_health_check():
    """
    Check Ollama LLM service availability.

    Returns availability status and configured model name for debugging.
    Always returns 200 OK, even when Ollama is unreachable (not a server error).
    Allows frontend to show "LLM offline" indicator or disable LLM features.

    Returns:
        dict: {"available": bool, "model": str}
    """
    client = OllamaClient()
    available = await client.is_available()
    await client.close()

    return {
        "available": available,
        "model": settings.ollama_model,
    }


if settings.environment == "local":

    @app.get("/debug/tables")
    async def debug_tables():
        engine = get_engine()
        inspector = inspect(engine)
        return {"tables": inspector.get_table_names()}
