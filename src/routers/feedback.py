"""
Feedback endpoints for FreshUp.

Users send notes to the developer from the account menu; the notes are stored
and read back while the app is being built.

Authorization:
- POST /feedback: any authenticated user
- GET /feedback: coordinators only
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from src.db.database import get_db
from src.db.models.feedback import Feedback
from src.db.models.user import User, UserRole
from src.middleware.auth import get_current_user
from src.schemas.feedback import FeedbackCreate, FeedbackResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


def _response(feedback: Feedback) -> FeedbackResponse:
    return FeedbackResponse(
        id=feedback.id,
        message=feedback.message,
        kind=feedback.kind or "other",
        page=feedback.page,
        created_at=feedback.created_at,
        user_name=feedback.user_rel.name,
    )


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def send_feedback(
    request: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    """Store a note to the developer from the signed-in user."""
    feedback = Feedback(
        user_id=current_user.id, message=request.message, page=request.page, kind=request.kind
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    logger.info("Feedback %s stored from user %s", feedback.id, current_user.id)
    return _response(feedback)


@router.get("", response_model=list[FeedbackResponse])
def list_feedback(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FeedbackResponse]:
    """Every stored note, newest first. Coordinators only."""
    if current_user.role != UserRole.coordinator.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a coordinator can read feedback",
        )
    rows = (
        db.query(Feedback)
        .options(joinedload(Feedback.user_rel))
        .order_by(Feedback.created_at.desc(), Feedback.id)
        .all()
    )
    return [_response(row) for row in rows]
