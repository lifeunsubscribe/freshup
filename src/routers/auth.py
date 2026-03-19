"""
Authentication endpoints for FreshUp.

Provides user registration and login endpoints with JWT token generation.
"""

import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from src.db.database import get_db
from src.db.models.user import User, UserRole
from src.schemas.auth import UserCreate, LoginRequest, UserResponse, TokenResponse, UserUpdate, SwitchUserRequest
from src.services.auth_service import hash_password, verify_password, create_access_token
from src.services.audit_service import log_registration, log_login_attempt, log_profile_update
from src.middleware.auth import get_current_user

logger = logging.getLogger(__name__)


# Pre-computed valid bcrypt hash for timing attack mitigation
# This is the hash of "dummy_password_for_timing_attack_protection"
DUMMY_PASSWORD_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYMwJR1fGKHi"

# Account lockout settings (OWASP recommendations)
MAX_FAILED_LOGIN_ATTEMPTS = 5
# Progressive lockout durations (exponential backoff) in minutes
# [1st lockout, 2nd lockout, 3rd lockout, 4th lockout, 5th+ lockout]
PROGRESSIVE_LOCKOUT_DURATIONS = [15, 30, 60, 120, 240]  # 15min, 30min, 1h, 2h, 4h (cap)

router = APIRouter(prefix="/auth", tags=["authentication"])


def get_lockout_duration(lockout_count: int) -> int:
    """
    Calculate the lockout duration based on the number of previous lockouts.

    Implements exponential backoff for account lockouts to progressively
    increase the difficulty of brute force attacks. Uses a capped schedule
    to prevent excessively long lockouts.

    Args:
        lockout_count: Number of times the account has been locked out previously

    Returns:
        Lockout duration in minutes

    Examples:
        >>> get_lockout_duration(0)  # First lockout
        15
        >>> get_lockout_duration(1)  # Second lockout
        30
        >>> get_lockout_duration(4)  # Fifth lockout
        240
        >>> get_lockout_duration(100)  # Exceeds schedule, uses cap
        240
    """
    if lockout_count < len(PROGRESSIVE_LOCKOUT_DURATIONS):
        return PROGRESSIVE_LOCKOUT_DURATIONS[lockout_count]
    # Use the maximum duration (cap) for any lockout beyond the schedule
    return PROGRESSIVE_LOCKOUT_DURATIONS[-1]


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, request: Request, db: Session = Depends(get_db)):
    """
    Register a new user.

    First-user coordinator logic: The first user to register in a fresh household
    automatically receives the 'coordinator' role regardless of the role field in
    the request. Subsequent registrations always default to 'member' to prevent
    unauthorized self-promotion to coordinator role.

    Args:
        user_data: User registration data (name, email, password, dietary_profile, allergies, role)
        request: FastAPI request object (for audit logging)
        db: Database session

    Returns:
        UserResponse: Created user data (excluding password)

    Raises:
        HTTPException(400): If email already exists
        HTTPException(422): If validation fails (invalid email format, password too short, etc.)
    """
    # Check if email already exists (email is normalized by schema validator)
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        # Log failed registration attempt (email already exists)
        log_registration(
            db=db,
            user_id=None,
            email=user_data.email,
            request=request,
            success=False,
            failure_reason="email_already_exists"
        )
        # Commit the audit log before raising exception
        try:
            db.commit()
        except SQLAlchemyError as e:
            # If audit log commit fails, rollback and log the error
            db.rollback()
            logger.error("Database error during registration audit logging (email exists)")
            logger.debug(f"Database error details: {str(e)}")
            # Fall through to raise the original validation error

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # First-user coordinator logic: if no users exist, make this user a coordinator
    user_count = db.query(func.count(User.id)).scalar()
    if user_count == 0:
        # First user - force coordinator role
        assigned_role = UserRole.coordinator.value
    else:
        # Subsequent users - always default to member (prevents self-promotion)
        assigned_role = UserRole.member.value

    # Hash the password
    hashed_password = hash_password(user_data.password)

    # Create new user
    new_user = User(
        name=user_data.name,
        email=user_data.email,
        hashed_password=hashed_password,
        role=assigned_role,
        dietary_profile=user_data.dietary_profile or [],
        allergies=user_data.allergies or [],
        disliked_ingredients=user_data.disliked_ingredients or [],
        favorite_ingredients=user_data.favorite_ingredients or [],
    )

    db.add(new_user)
    db.flush()  # Flush to get the user ID for audit logging

    # Log successful registration (before commit so it's in the same transaction)
    log_registration(
        db=db,
        user_id=new_user.id,
        email=new_user.email,
        request=request,
        success=True,
        metadata={"role": assigned_role}
    )

    try:
        db.commit()
        db.refresh(new_user)
    except IntegrityError as e:
        # Handle database constraint violations (e.g., unique constraint on email)
        db.rollback()
        logger.error("Integrity error during user registration")
        logger.debug(f"Integrity error details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User registration failed due to data integrity violation"
        )
    except SQLAlchemyError as e:
        # Handle general database errors
        db.rollback()
        logger.error("Database error during user registration")
        logger.debug(f"Database error details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the user account"
        )

    return new_user


@router.post("/login", response_model=TokenResponse)
def login(login_data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """
    Authenticate a user and return a JWT access token.

    Implements progressive account lockout mechanism to prevent brute force attacks:
    - Locks account after 5 failed login attempts
    - Uses exponential backoff for lockout duration (15min, 30min, 1h, 2h, 4h cap)
    - Increases lockout duration with each subsequent lockout event
    - Resets lockout counter on successful login
    - Returns generic error messages to avoid leaking account existence

    Args:
        login_data: Login credentials (email, password)
        request: FastAPI request object (for audit logging)
        db: Database session

    Returns:
        TokenResponse: JWT access token

    Raises:
        HTTPException(401): If credentials are invalid or account is locked
    """
    # Query user by email (email is normalized by schema validator)
    user = db.query(User).filter(User.email == login_data.email).first()

    # Verify user exists and password is correct
    # Use generic error message to avoid leaking whether email exists
    # Perform dummy password verification for non-existent users to prevent timing attacks
    if not user or not user.hashed_password:
        # Run a dummy password verification to match timing of real verification
        verify_password(login_data.password, DUMMY_PASSWORD_HASH)

        # Log failed login attempt (user not found)
        log_login_attempt(
            db=db,
            email=login_data.email,
            request=request,
            success=False,
            failure_reason="invalid_credentials"
        )
        # Commit the audit log before raising exception
        try:
            db.commit()
        except SQLAlchemyError as e:
            # If audit log commit fails, rollback and log the error
            db.rollback()
            logger.error("Database error during login audit logging (user not found)")
            logger.debug(f"Database error details: {str(e)}")
            # Fall through to raise the original authentication error

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password FIRST (before lockout check) to prevent timing attacks
    # This ensures constant-time operation regardless of lockout status
    password_valid = verify_password(login_data.password, user.hashed_password)

    # Check if account is currently locked
    now = datetime.now(timezone.utc)
    # Convert lockout_until to timezone-aware if it's naive (SQLite stores without tz)
    lockout_until = user.lockout_until
    if lockout_until and lockout_until.tzinfo is None:
        lockout_until = lockout_until.replace(tzinfo=timezone.utc)

    # If lockout has expired, reset the failed attempts counter
    if lockout_until and lockout_until <= now:
        user.failed_login_attempts = 0
        user.lockout_until = None
        lockout_until = None

    # Check if account is still locked after expiry check
    if lockout_until and lockout_until > now:
        # Account is locked - return generic error to avoid leaking account status
        log_login_attempt(
            db=db,
            email=login_data.email,
            request=request,
            success=False,
            user_id=user.id,
            failure_reason="account_locked"
        )
        # Commit the audit log before raising exception
        try:
            db.commit()
        except SQLAlchemyError as e:
            # If audit log commit fails, rollback and log the error
            db.rollback()
            logger.error("Database error during login audit logging (account locked)")
            logger.debug(f"Database error details: {str(e)}")
            # Fall through to raise the original authentication error

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check password validity (already verified above to prevent timing attacks)
    if not password_valid:
        # Increment failed login attempts
        user.failed_login_attempts += 1

        # Lock account if threshold reached
        if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
            # Progressive lockout: duration increases with each lockout event
            # lockout_count tracks how many times this user has been locked out before
            # get_lockout_duration uses lockout_count to determine duration (15min, 30min, 1h, 2h, 4h)
            lockout_duration_minutes = get_lockout_duration(user.lockout_count)
            user.lockout_until = now + timedelta(minutes=lockout_duration_minutes)
            # Increment lockout_count so next lockout will have longer duration (exponential backoff)
            user.lockout_count += 1
            logger.warning(
                "Account locked due to failed login attempts: user_id=%s, email=%s, attempts=%d, "
                "lockout_count=%d, duration=%d minutes",
                user.id,
                user.email,
                user.failed_login_attempts,
                user.lockout_count,
                lockout_duration_minutes
            )

        # Log failed login attempt (invalid password) - before commit so it's in same transaction
        log_login_attempt(
            db=db,
            email=login_data.email,
            request=request,
            success=False,
            failure_reason="invalid_credentials"
        )

        # Commit failed login attempt state and audit log together
        db.commit()

        # Return generic error message
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Successful login - reset all lockout fields including progressive counter
    user.failed_login_attempts = 0
    user.lockout_until = None
    user.lockout_count = 0  # Reset progressive lockout counter on successful login

    # Log successful login (before commit so it's in the same transaction)
    log_login_attempt(
        db=db,
        email=login_data.email,
        request=request,
        success=True,
        user_id=user.id
    )

    # Commit successful login state and audit log together
    db.commit()

    # Create JWT token with user ID in the 'sub' claim
    access_token = create_access_token(data={"sub": str(user.id)})

    return TokenResponse(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get the authenticated user's profile.

    Returns the full user profile for the authenticated user. Requires a valid
    JWT token in the Authorization header.

    Args:
        current_user: Authenticated user (injected by get_current_user dependency)

    Returns:
        UserResponse: User profile data (excluding password)

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
    """
    return current_user


@router.put("/me", response_model=UserResponse)
def update_current_user_profile(
    update_data: UserUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update the authenticated user's profile.

    Allows users to update their own profile information including name, dietary
    preferences, allergies, and ingredient preferences. Email and role updates
    are not permitted through this endpoint.

    Args:
        update_data: Profile fields to update (all fields optional)
        request: FastAPI request object (for audit logging)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        UserResponse: Updated user profile data (excluding password)

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(422): If validation fails (invalid dietary profile, empty name, etc.)
    """
    # Explicit allowlist of fields that can be updated via this endpoint
    # Security: role and email can NEVER be updated here to prevent privilege escalation
    ALLOWED_UPDATE_FIELDS = {
        "name",
        "dietary_profile",
        "allergies",
        "disliked_ingredients",
        "favorite_ingredients"
    }

    PROTECTED_FIELDS = {"email", "role"}

    # Update only the fields that were provided (partial updates)
    update_dict = update_data.model_dump(exclude_unset=True)

    # Log the profile update attempt with requested fields
    logger.debug(
        "Profile update attempt by user %s (email: %s) with fields: %s",
        current_user.id,
        current_user.email,
        list(update_dict.keys())
    )

    # Track which fields were actually updated for audit log
    fields_updated = []

    for field, value in update_dict.items():
        if field not in ALLOWED_UPDATE_FIELDS:
            # Log attempts to modify protected fields for security monitoring
            if field in PROTECTED_FIELDS:
                logger.warning(
                    "Attempted modification of protected field '%s' by user %s (email: %s). "
                    "This may indicate a privilege escalation attempt.",
                    field,
                    current_user.id,
                    current_user.email
                )
            # Silently skip disallowed fields for defense-in-depth
            continue
        setattr(current_user, field, value)
        fields_updated.append(field)

    # Log profile update to audit log (before commit so it's in the same transaction)
    if fields_updated:
        log_profile_update(
            db=db,
            user_id=current_user.id,
            email=current_user.email,
            request=request,
            fields_updated=fields_updated
        )

    try:
        db.commit()
        db.refresh(current_user)
    except IntegrityError as e:
        # Handle database constraint violations
        db.rollback()
        logger.error(f"Integrity error during profile update for user {current_user.id}")
        logger.debug(f"Integrity error details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile update failed due to data integrity violation"
        )
    except SQLAlchemyError as e:
        # Handle general database errors
        db.rollback()
        logger.error(f"Database error during profile update for user {current_user.id}")
        logger.debug(f"Database error details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the profile"
        )

    # Log successful profile update with applied fields
    logger.info(
        "Profile updated successfully for user %s (email: %s). Updated fields: %s",
        current_user.id,
        current_user.email,
        fields_updated
    )

    return current_user


@router.post("/switch-user", response_model=TokenResponse)
def switch_user(
    switch_data: SwitchUserRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Switch active user session on a shared device.

    This endpoint enables the household trust model for shared device sessions
    (e.g., iPad kitchen terminal). Any authenticated user can switch to another
    household member's session without re-entering passwords. This is designed
    for the "who are you?" selector flow on shared devices.

    Args:
        switch_data: Target user ID to switch to
        current_user: Currently authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        TokenResponse: New JWT access token for the target user

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(403): If target user is not in the same household
        HTTPException(404): If target user does not exist

    Security Note:
        This endpoint intentionally does not require password authentication,
        following the household trust model described in FreshUp-ADR.md Section 1C.
        It assumes physical device access implies household membership trust.
        IMPORTANT: Only allows switching to users within the same household.
    """
    # Query target user by ID
    target_user = db.query(User).filter(User.id == switch_data.user_id).first()

    # Return 404 if target user doesn't exist
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Prevent switching to self (unnecessary token generation)
    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot switch to current user"
        )

    # SECURITY: Household Membership Verification
    # This endpoint implements the "household trust model" where any authenticated user
    # can switch to another user's session WITHOUT a password - but ONLY if both users
    # belong to the same household.
    #
    # Current Architecture (Phase 1): Single-household deployment
    # - No household_id field exists in the User model
    # - All users in the database implicitly belong to the same household
    # - Household boundary is enforced at deployment level (one database per household)
    # - Therefore, if target_user exists in the database, they're in current_user's household
    #
    # CRITICAL: When multi-household support is added (see ADR Section 11 "Multi-household support"):
    # - Add household_id field to User model
    # - UNCOMMENT the verification code below
    # - This check prevents horizontal privilege escalation across household boundaries
    #
    # The assertion below will fail if household_id is added but this security check is not updated.
    # This prevents accidentally deploying multi-household support without fixing this vulnerability.

    # Verify we're in single-household mode (no household_id field exists yet)
    if hasattr(current_user, 'household_id'):
        error_msg = (
            "SECURITY: household_id field detected on User model. "
            "Multi-household support requires explicit household membership verification. "
            "Uncomment and implement the household_id check below before deploying."
        )
        logger.error(error_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Service configuration error"
        )

    if hasattr(target_user, 'household_id'):
        error_msg = (
            "SECURITY: household_id field detected on User model. "
            "Multi-household support requires explicit household membership verification. "
            "Uncomment and implement the household_id check below before deploying."
        )
        logger.error(error_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Service configuration error"
        )

    # When multi-household support is added, UNCOMMENT AND IMPLEMENT this check:
    # if current_user.household_id != target_user.household_id:
    #     logger.warning(
    #         "SECURITY: Attempted cross-household user switch blocked. "
    #         "User %s (household %s) tried to switch to user %s (household %s)",
    #         current_user.id,
    #         current_user.household_id,
    #         target_user.id,
    #         target_user.household_id
    #     )
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Cannot switch to user in different household"
    #     )

    # Create JWT token for the target user
    access_token = create_access_token(data={"sub": str(target_user.id)})

    return TokenResponse(access_token=access_token, token_type="bearer")
