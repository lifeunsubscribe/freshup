"""
Authentication endpoints for FreshUp.

Provides user registration and login endpoints with JWT token generation.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.db.database import get_db
from src.db.models.user import User, UserRole
from src.schemas.auth import UserCreate, LoginRequest, UserResponse, TokenResponse
from src.services.auth_service import hash_password, verify_password, create_access_token


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user.

    First-user coordinator logic: The first user to register in a fresh household
    automatically receives the 'coordinator' role regardless of the role field in
    the request. Subsequent registrations default to 'member' if role is not specified.

    Args:
        user_data: User registration data (name, email, password, dietary_profile, allergies, role)
        db: Database session

    Returns:
        UserResponse: Created user data (excluding password)

    Raises:
        HTTPException(400): If email already exists
        HTTPException(422): If validation fails (invalid email format, password too short, etc.)
    """
    # Check if email already exists
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
        # Subsequent users - use provided role or default to member
        assigned_role = user_data.role if user_data.role else UserRole.member.value

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
    # Query user by email
    user = db.query(User).filter(User.email == login_data.email).first()

    # Verify user exists and password is correct
    # Use generic error message to avoid leaking whether email exists
    if not user or not user.hashed_password:
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
