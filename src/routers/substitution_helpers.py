"""
Helper functions for substitution preference ownership verification.

Centralizes ownership validation logic to reduce code duplication across
substitution CRUD endpoints and maintain consistent error handling.
"""

from uuid import UUID
from sqlalchemy.orm import Session

from src.db.models.user import User
from src.db.models.substitution import SubstitutionPreference
from src.utils.ownership import verify_ownership


def verify_substitution_preference_ownership(
    preference_id: UUID,
    current_user: User,
    db: Session,
) -> SubstitutionPreference:
    """
    Verify that a substitution preference exists and belongs to the current user.

    Used by update and delete endpoints that enforce ownership at the
    database query level for efficiency.

    Args:
        preference_id: UUID of the substitution preference to verify
        current_user: Authenticated user making the request
        db: Database session

    Returns:
        SubstitutionPreference: The preference if it exists and belongs to current user

    Raises:
        HTTPException(404): If preference doesn't exist or belongs to another user
    """
    return verify_ownership(
        entity_class=SubstitutionPreference,
        entity_id=preference_id,
        ownership_field='user_id',
        current_user=current_user,
        db=db,
        entity_name="Substitution preference"
    )
