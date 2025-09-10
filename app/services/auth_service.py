"""
Authentication service for user registration, login, and token management.
"""
from typing import Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import SecurityUtils
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserLogin, UserRegister, TokenResponse
from app.schemas.user import UserCreate


class AuthService:
    """Authentication service for user management and token operations."""
    
    def __init__(self, db: Session):
        """
        Initialize authentication service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.user_repo = UserRepository(db)
    
    def register_user(self, user_data: UserRegister) -> Dict[str, str]:
        """
        Register a new user account.
        
        Args:
            user_data: User registration data
            
        Returns:
            Dictionary containing access and refresh tokens
            
        Raises:
            HTTPException: If email is already registered
        """
        # Check if email is already registered
        if self.user_repo.is_email_taken(user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password
        hashed_password = SecurityUtils.get_password_hash(user_data.password)
        
        # Create user data
        user_create_data = {
            "email": user_data.email,
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
            "hashed_password": hashed_password,
            "role": UserRole.USER,
            "is_active": True,
            "is_verified": False
        }
        
        # Create user
        user = self.user_repo.create_user(user_create_data)
        
        # Generate tokens
        return SecurityUtils.create_token_pair(str(user.id))
    
    def authenticate_user(self, login_data: UserLogin) -> Dict[str, str]:
        """
        Authenticate user and return tokens.
        
        Args:
            login_data: User login credentials
            
        Returns:
            Dictionary containing access and refresh tokens
            
        Raises:
            HTTPException: If authentication fails
        """
        # Authenticate user
        user = self.user_repo.authenticate(login_data.email, login_data.password)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is deactivated"
            )
        
        # Generate tokens
        return SecurityUtils.create_token_pair(str(user.id))
    
    def refresh_token(self, refresh_token: str) -> Dict[str, str]:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            Dictionary containing new access and refresh tokens
            
        Raises:
            HTTPException: If refresh token is invalid
        """
        # Verify refresh token
        user_id = SecurityUtils.get_subject_from_token(refresh_token, "refresh")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user exists and is active
        user = self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Generate new token pair (token rotation)
        return SecurityUtils.create_token_pair(str(user.id))
    
    def change_password(
        self, 
        user: User, 
        current_password: str, 
        new_password: str
    ) -> bool:
        """
        Change user password.
        
        Args:
            user: Current user
            current_password: Current password
            new_password: New password
            
        Returns:
            True if password changed successfully
            
        Raises:
            HTTPException: If current password is incorrect
        """
        # Verify current password
        if not SecurityUtils.verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect current password"
            )
        
        # Hash new password
        new_hashed_password = SecurityUtils.get_password_hash(new_password)
        
        # Update user password
        self.user_repo.update(user, {"hashed_password": new_hashed_password})
        
        return True
    
    def get_user_info(self, user: User) -> Dict:
        """
        Get user information for token payload.
        
        Args:
            user: User instance
            
        Returns:
            Dictionary with user information
        """
        return {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role.value,
            "is_active": user.is_active,
            "is_verified": user.is_verified
        }
    
    def verify_user_email(self, user_id: str) -> Optional[User]:
        """
        Verify user email address.
        
        Args:
            user_id: User ID to verify
            
        Returns:
            Updated user instance if successful
        """
        return self.user_repo.verify_user_email(user_id)
    
    def deactivate_user(self, user_id: str) -> Optional[User]:
        """
        Deactivate user account (admin only).
        
        Args:
            user_id: User ID to deactivate
            
        Returns:
            Updated user instance if successful
        """
        return self.user_repo.deactivate_user(user_id)
    
    def activate_user(self, user_id: str) -> Optional[User]:
        """
        Activate user account (admin only).
        
        Args:
            user_id: User ID to activate
            
        Returns:
            Updated user instance if successful
        """
        return self.user_repo.activate_user(user_id)