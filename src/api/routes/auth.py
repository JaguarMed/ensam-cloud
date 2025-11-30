"""
Authentication routes.

Implements EF1: User authentication with JWT issuance.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
import logging

from ...core.config import settings
from ...core.database import get_db
from ...core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user
)
from ...models import User
from ...schemas import (
    LoginRequest, LoginResponse,
    RegisterRequest, UserResponse,
    ErrorResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
async def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT token.
    
    - **email**: User's email address
    - **password**: User's password
    
    Returns JWT access token on successful authentication.
    """
    # Find user by email
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user or not verify_password(credentials.password, user.password_hash):
        logger.warning(f"Failed login attempt for: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "name": user.full_name or user.email,
            "is_admin": user.is_admin
        },
        expires_delta=access_token_expires
    )
    
    logger.info(f"User logged in: {user.email}")
    
    return LoginResponse(
        success=True,
        token=access_token,
        user=user.to_dict(),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        message="Login successful"
    )


@router.post("/login/form", response_model=LoginResponse)
async def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    OAuth2 compatible login endpoint for form-based authentication.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=access_token_expires
    )
    
    return LoginResponse(
        success=True,
        token=access_token,
        user=user.to_dict(),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        message="Login successful"
    )


@router.post("/register", response_model=UserResponse)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.
    
    - **email**: Unique email address
    - **password**: Password (min 6 characters)
    - **full_name**: Optional display name
    """
    # Check if email already exists
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user = User(
        email=request.email,
        password_hash=get_password_hash(request.password),
        full_name=request.full_name,
        is_active=True,
        is_admin=False
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    logger.info(f"New user registered: {user.email}")
    
    return UserResponse.model_validate(user)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user information.
    """
    return UserResponse.model_validate(current_user)


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout current user.
    
    Note: JWT tokens are stateless, so this endpoint just confirms logout.
    Client should remove the token from storage.
    """
    return {"success": True, "message": "Logged out successfully"}








