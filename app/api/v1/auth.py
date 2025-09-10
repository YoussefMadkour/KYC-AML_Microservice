"""
Authentication API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.core.config import settings
from app.models.user import User
from app.schemas.auth import (
    UserLogin, 
    UserRegister, 
    TokenResponse, 
    TokenRefresh, 
    PasswordChange,
    UserInfo
)
from app.services.auth_service import AuthService


router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.
    
    Creates a new user account with the provided information and returns
    JWT access and refresh tokens for immediate authentication.
    
    Args:
        user_data: User registration information
        db: Database session
        
    Returns:
        JWT tokens for the newly created user
        
    Raises:
        HTTPException: If email is already registered or validation fails
    """
    auth_service = AuthService(db)
    tokens = auth_service.register_user(user_data)
    
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT tokens.
    
    Validates user credentials and returns JWT access and refresh tokens
    for authenticated sessions.
    
    Args:
        login_data: User login credentials
        db: Database session
        
    Returns:
        JWT tokens for the authenticated user
        
    Raises:
        HTTPException: If credentials are invalid or user is inactive
    """
    auth_service = AuthService(db)
    tokens = auth_service.authenticate_user(login_data)
    
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_data: TokenRefresh,
    db: Session = Depends(get_db)
):
    """
    Refresh JWT access token using refresh token.
    
    Validates the provided refresh token and returns new JWT access and
    refresh tokens. This implements secure token rotation.
    
    Args:
        token_data: Refresh token data
        db: Database session
        
    Returns:
        New JWT tokens
        
    Raises:
        HTTPException: If refresh token is invalid or expired
    """
    auth_service = AuthService(db)
    tokens = auth_service.refresh_token(token_data.refresh_token)
    
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Change user password.
    
    Allows authenticated users to change their password by providing
    their current password and a new password.
    
    Args:
        password_data: Current and new password data
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If current password is incorrect
    """
    auth_service = AuthService(db)
    auth_service.change_password(
        current_user,
        password_data.current_password,
        password_data.new_password
    )
    
    return {"message": "Password changed successfully"}


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user information.
    
    Returns information about the currently authenticated user.
    
    Args:
        current_user: Currently authenticated user
        
    Returns:
        Current user information
    """
    return UserInfo(
        id=str(current_user.id),
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        role=current_user.role.value,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout():
    """
    Logout user.
    
    Since JWT tokens are stateless, logout is handled client-side by
    discarding the tokens. This endpoint exists for API completeness
    and could be extended to implement token blacklisting if needed.
    
    Returns:
        Success message
    """
    return {"message": "Successfully logged out"}


@router.get("/verify-token", status_code=status.HTTP_200_OK)
async def verify_token(
    current_user: User = Depends(get_current_active_user)
):
    """
    Verify JWT token validity.
    
    Endpoint to verify if the provided JWT token is valid and the user
    is active. Useful for client-side token validation.
    
    Args:
        current_user: Currently authenticated user
        
    Returns:
        Token validity confirmation
    """
    return {
        "valid": True,
        "user_id": str(current_user.id),
        "email": current_user.email
    }