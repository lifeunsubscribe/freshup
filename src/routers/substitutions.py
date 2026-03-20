"""
SubstitutionPreference CRUD endpoints for FreshUp.

Provides endpoints for users to manage their ingredient substitution preferences.
All endpoints are scoped to the authenticated user (/users/me/substitutions).

Logging Policy:
    User-provided ingredient names are NOT logged as they may contain sensitive
    health information (e.g., allergens, dietary restrictions, medical conditions).
    Logs include operational metadata (user_id, preference_id, timestamps) for
    debugging while protecting user privacy per OWASP recommendations.
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from src.db.database import get_db
from src.db.models.user import User
from src.db.models.substitution import SubstitutionPreference
from src.schemas.substitution import (
    SubstitutionPreferenceCreate,
    SubstitutionPreferenceUpdate,
    SubstitutionPreferenceResponse,
)
from src.middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users/me/substitutions", tags=["substitutions"])


@router.post("", response_model=SubstitutionPreferenceResponse, status_code=status.HTTP_201_CREATED)
def create_substitution_preference(
    preference_data: SubstitutionPreferenceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new substitution preference for the authenticated user.

    Allows users to define per-ingredient replacement preferences with ranked
    alternatives and optional context (side_dish, in_recipe, protein, sauce, any).

    Args:
        preference_data: Substitution preference data (original_ingredient, replacements, context)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        SubstitutionPreferenceResponse: Created substitution preference

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(422): If validation fails (invalid replacements format, invalid context, etc.)
    """
    # Convert ReplacementItem objects to dict format for JSON storage
    replacements_json = [
        {"ingredient": item.ingredient, "rank": item.rank}
        for item in preference_data.replacements
    ]

    # Create new substitution preference
    new_preference = SubstitutionPreference(
        user_id=current_user.id,
        original_ingredient=preference_data.original_ingredient,
        replacements=replacements_json,
        context=preference_data.context,
    )

    db.add(new_preference)

    try:
        db.commit()
        db.refresh(new_preference)
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error during substitution preference creation for user {current_user.id}")
        logger.debug(f"Integrity error details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Substitution preference creation failed due to data integrity violation"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during substitution preference creation for user {current_user.id}")
        logger.debug(f"Database error details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the substitution preference"
        )

    logger.info(
        f"Substitution preference created: user_id={current_user.id}, "
        f"preference_id={new_preference.id}"
    )

    return new_preference


@router.get("", response_model=list[SubstitutionPreferenceResponse])
def list_substitution_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all substitution preferences for the authenticated user.

    Returns all ingredient substitution preferences created by the current user,
    ordered by original ingredient name.

    Note: This endpoint intentionally does not implement pagination. The 20-replacement
    limit per preference and typical user behavior (managing a small set of personal
    substitution rules) bounds the data size. Pagination can be added as a future
    enhancement if usage patterns indicate need.

    Args:
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        list[SubstitutionPreferenceResponse]: List of all user's substitution preferences

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
    """
    preferences = (
        db.query(SubstitutionPreference)
        .filter(SubstitutionPreference.user_id == current_user.id)
        .order_by(SubstitutionPreference.original_ingredient)
        .all()
    )

    return preferences


@router.get("/{preference_id}", response_model=SubstitutionPreferenceResponse)
def get_substitution_preference(
    preference_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a single substitution preference by ID.

    Retrieves a specific substitution preference. Returns 404 if the preference
    doesn't exist or belongs to a different user (preventing cross-user access).

    Args:
        preference_id: UUID of the substitution preference to retrieve
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        SubstitutionPreferenceResponse: Requested substitution preference

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If preference doesn't exist or belongs to another user
    """
    preference = (
        db.query(SubstitutionPreference)
        .filter(
            SubstitutionPreference.id == preference_id,
            SubstitutionPreference.user_id == current_user.id,
        )
        .first()
    )

    if not preference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Substitution preference not found"
        )

    return preference


@router.put("/{preference_id}", response_model=SubstitutionPreferenceResponse)
def update_substitution_preference(
    preference_id: UUID,
    update_data: SubstitutionPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update a substitution preference's replacements or context.

    Allows partial updates - only provided fields will be updated. Returns 404
    if the preference doesn't exist or belongs to a different user.

    Args:
        preference_id: UUID of the substitution preference to update
        update_data: Fields to update (replacements, context)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        SubstitutionPreferenceResponse: Updated substitution preference

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If preference doesn't exist or belongs to another user
        HTTPException(422): If validation fails (invalid replacements format, invalid context, etc.)
    """
    # Query preference with user ownership check
    preference = (
        db.query(SubstitutionPreference)
        .filter(
            SubstitutionPreference.id == preference_id,
            SubstitutionPreference.user_id == current_user.id,
        )
        .first()
    )

    if not preference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Substitution preference not found"
        )

    # Update only the fields that were provided
    update_dict = update_data.model_dump(exclude_unset=True)

    # Convert replacements to JSON format if provided
    if "replacements" in update_dict and update_dict["replacements"] is not None:
        update_dict["replacements"] = [
            {"ingredient": item.ingredient, "rank": item.rank}
            for item in update_data.replacements
        ]

    # Apply updates
    for field, value in update_dict.items():
        setattr(preference, field, value)

    try:
        db.commit()
        db.refresh(preference)
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error during substitution preference update for user {current_user.id}")
        logger.debug(f"Integrity error details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Substitution preference update failed due to data integrity violation"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during substitution preference update for user {current_user.id}")
        logger.debug(f"Database error details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the substitution preference"
        )

    logger.info(
        f"Substitution preference updated: user_id={current_user.id}, "
        f"preference_id={preference_id}"
    )

    return preference


@router.delete("/{preference_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_substitution_preference(
    preference_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a substitution preference.

    Removes the specified substitution preference. Returns 404 if the preference
    doesn't exist or belongs to a different user.

    Args:
        preference_id: UUID of the substitution preference to delete
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        None (204 No Content on success)

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If preference doesn't exist or belongs to another user
    """
    # Query preference with user ownership check
    preference = (
        db.query(SubstitutionPreference)
        .filter(
            SubstitutionPreference.id == preference_id,
            SubstitutionPreference.user_id == current_user.id,
        )
        .first()
    )

    if not preference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Substitution preference not found"
        )

    try:
        db.delete(preference)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during substitution preference deletion for user {current_user.id}")
        logger.debug(f"Database error details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the substitution preference"
        )

    logger.info(
        f"Substitution preference deleted: user_id={current_user.id}, "
        f"preference_id={preference_id}"
    )

    return None
