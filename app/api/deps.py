"""
FastAPI dependencies for authentication and authorization.
"""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import SecurityUtils
from app.database import get_db
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository

# HTTP Bearer token security scheme
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Get the current authenticated user from JWT token.

    Args:
        credentials: HTTP Bearer credentials
        db: Database session

    Returns:
        Current user object

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Extract and verify token
    token = credentials.credentials
    user_id = SecurityUtils.get_subject_from_token(token, "access")

    if user_id is None:
        raise credentials_exception

    # Get user from database
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user"
        )

    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Get the current active user.

    Args:
        current_user: Current user from get_current_user dependency

    Returns:
        Current active user

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    return current_user


def get_current_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Get the current user if they are an admin.

    Args:
        current_user: Current active user

    Returns:
        Current admin user

    Raises:
        HTTPException: If user is not an admin
    """
    if not current_user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )
    return current_user


def get_current_compliance_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Get the current user if they are a compliance officer or admin.

    Args:
        current_user: Current active user

    Returns:
        Current compliance user

    Raises:
        HTTPException: If user is not compliance officer or admin
    """
    if not (current_user.is_compliance_officer() or current_user.is_admin()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )
    return current_user


def require_role(required_role: UserRole):
    """
    Create a dependency that requires a specific user role.

    Args:
        required_role: The required user role

    Returns:
        Dependency function that checks user role
    """

    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role != required_role and not current_user.is_admin():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required",
            )
        return current_user

    return role_checker


def require_roles(*required_roles: UserRole):
    """
    Create a dependency that requires one of multiple user roles.

    Args:
        required_roles: The required user roles

    Returns:
        Dependency function that checks user roles
    """

    def roles_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in required_roles and not current_user.is_admin():
            roles_str = "', '".join(required_roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of roles '{roles_str}' required",
            )
        return current_user

    return roles_checker


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Get the current user if authenticated, otherwise return None.

    Args:
        credentials: Optional HTTP Bearer credentials
        db: Database session

    Returns:
        Current user object if authenticated, None otherwise
    """
    if not credentials:
        return None

    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None


def require_admin_or_self(current_user: User, target_user_id: UUID) -> None:
    """
    Require that the current user is either an admin or the target user.

    Args:
        current_user: The current authenticated user
        target_user_id: The UUID of the target user

    Raises:
        HTTPException: If user is not admin and not the target user
    """
    if not current_user.is_admin() and current_user.id != target_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own data or be an administrator",
        )
