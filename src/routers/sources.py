"""
Source health endpoints for FreshUp.

Exposes the daily health check results so the frontend can show a status
row per source and a calm alert on the add-a-recipe screen.

Authorization:
- GET /sources/health: Any authenticated user, no rate limit
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models.user import User
from src.middleware.auth import get_current_user
from src.schemas.source_health import SourceStatusResponse
from src.services.source_health_service import latest_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("/health", response_model=list[SourceStatusResponse])
def get_source_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SourceStatusResponse]:
    """
    Return the latest health status for each monitored recipe source.

    Any authenticated user may call this endpoint.
    Sources not yet checked report status='never_checked'.
    """
    logger.debug(f"User {current_user.id} requesting source health status")
    return latest_status(db)
