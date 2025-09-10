"""
User repository for database operations.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.repositories.base import BaseRepository
from app.schemas.user import UserCreate, UserUpdate


class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    """User repository with user-specific operations."""

    def __init__(self, db: Session):
        """Initialize user repository."""
        super().__init__(User, db)

    def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address.

        Args:
            email: User email address

        Returns:
            User instance if found, None otherwise
        """
        return self.db.query(User).filter(User.email == email).first()

    def create_user(self, user_data: dict) -> User:
        """
        Create a new user with hashed password.

        Args:
            user_data: Dictionary containing user data

        Returns:
            Created user instance
        """
        return self.create_from_dict(user_data)

    def authenticate(self, email: str, password: str) -> Optional[User]:
        """
        Authenticate user by email and password.

        Args:
            email: User email address
            password: Plain text password

        Returns:
            User instance if authentication successful, None otherwise
        """
        from app.core.security import SecurityUtils

        user = self.get_by_email(email)
        if not user:
            return None

        if not SecurityUtils.verify_password(password, user.hashed_password):
            return None

        return user

    def is_email_taken(self, email: str, exclude_user_id: Optional[str] = None) -> bool:
        """
        Check if email is already taken by another user.

        Args:
            email: Email address to check
            exclude_user_id: Optional user ID to exclude from check

        Returns:
            True if email is taken, False otherwise
        """
        query = self.db.query(User).filter(User.email == email)

        if exclude_user_id:
            query = query.filter(User.id != exclude_user_id)

        return query.first() is not None

    def get_active_users(self, skip: int = 0, limit: int = 100):
        """
        Get active users with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of active users
        """
        return self.get_multi(skip=skip, limit=limit, is_active=True)

    def get_users_by_role(self, role: UserRole, skip: int = 0, limit: int = 100):
        """
        Get users by role with pagination.

        Args:
            role: User role to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of users with specified role
        """
        return self.get_multi(skip=skip, limit=limit, role=role)

    def deactivate_user(self, user_id: str) -> Optional[User]:
        """
        Deactivate a user account.

        Args:
            user_id: User ID to deactivate

        Returns:
            Updated user instance if found, None otherwise
        """
        user = self.get_by_id(user_id)
        if user:
            return self.update(user, {"is_active": False})
        return None

    def activate_user(self, user_id: str) -> Optional[User]:
        """
        Activate a user account.

        Args:
            user_id: User ID to activate

        Returns:
            Updated user instance if found, None otherwise
        """
        user = self.get_by_id(user_id)
        if user:
            return self.update(user, {"is_active": True})
        return None

    def verify_user_email(self, user_id: str) -> Optional[User]:
        """
        Mark user email as verified.

        Args:
            user_id: User ID to verify

        Returns:
            Updated user instance if found, None otherwise
        """
        user = self.get_by_id(user_id)
        if user:
            return self.update(user, {"is_verified": True})
        return None

    async def get_by_id(self, user_id) -> Optional[User]:
        """
        Get user by ID (async version).

        Args:
            user_id: User ID

        Returns:
            User instance if found, None otherwise
        """
        return super().get(user_id)

    async def update(self, user_id, user: User) -> Optional[User]:
        """
        Update user (async version).

        Args:
            user_id: User ID
            user: Updated user data

        Returns:
            Updated user instance if found, None otherwise
        """
        existing_user = self.get(user_id)
        if not existing_user:
            return None

        # Update fields
        for key, value in user.__dict__.items():
            if not key.startswith("_") and hasattr(existing_user, key):
                setattr(existing_user, key, value)

        self.db.commit()
        self.db.refresh(existing_user)
        return existing_user
