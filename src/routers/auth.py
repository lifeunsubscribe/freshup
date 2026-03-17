"""
Authentication endpoints for FreshUp.

Provides user registration and login endpoints with JWT token generation.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.db.database import get_db
from src.db.models.user import User, UserRole
from src.schemas.auth import UserCreate, LoginRequest, UserResponse, TokenResponse, UserUpdate
from src.services.auth_service import hash_password, verify_password, create_access_token
from src.middleware.auth import get_current_user


# Pre-computed valid bcrypt hash for timing attack mitigation
# This is the hash of "dummy_password_for_timing_attack_protection"
DUMMY_PASSWORD_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYMwJR1fGKHi"

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user.

    First-user coordinator logic: The first user to register in a fresh household
    automatically receives the 'coordinator' role regardless of the role field in
    the request. Subsequent registrations always default to 'member' to prevent
    unauthorized self-promotion to coordinator role.

    Args:
        user_data: User registration data (name, email, password, dietary_profile, allergies, role)
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
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post("/login", response_model=TokenResponse)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate a user and return a JWT access token.

    Args:
        login_data: Login credentials (email, password)
        db: Database session

    Returns:
        TokenResponse: JWT access token

    Raises:
        HTTPException(401): If credentials are invalid (generic message to avoid
                           leaking whether email exists)
    """
    # Query user by email (email is normalized by schema validator)
    user = db.query(User).filter(User.email == login_data.email).first()

    # Verify user exists and password is correct
    # Use generic error message to avoid leaking whether email exists
    # Perform dummy password verification for non-existent users to prevent timing attacks
    if not user or not user.hashed_password:
        # Run a dummy password verification to match timing of real verification
        verify_password(login_data.password, DUMMY_PASSWORD_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

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
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        UserResponse: Updated user profile data (excluding password)

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(422): If validation fails (invalid dietary profile, empty name, etc.)
    """
    # Update only the fields that were provided (partial updates)
    update_dict = update_data.model_dump(exclude_unset=True)

    for field, value in update_dict.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)

    return current_user
