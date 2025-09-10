"""
User management API endpoints.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_active_user,
    get_current_admin_user,
    get_db
)
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserResponse, UserProfile, UserUpdate, UserAdminUpdate
from app.services.auth_service import AuthService


router = APIRouter()


@router.get("/profile", response_model=UserProfile)
async def get_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user's profile.
    
    Returns the complete profile information for the currently
    authenticated user.
    
    Args:
        current_user: Currently authenticated user
        
    Returns:
        User profile information
    """
    return UserProfile(
        id=str(current_user.id),
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        date_of_birth=current_user.date_of_birth,
        phone_number=current_user.phone_number,
        role=current_user.role,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        address_line1=current_user.address_line1,
        address_line2=current_user.address_line2,
        city=current_user.city,
        state_province=current_user.state_province,
        postal_code=current_user.postal_code,
        country=current_user.country,
        created_at=current_user.created_at.isoformat(),
        updated_at=current_user.updated_at.isoformat(),
        full_name=current_user.full_name,
        full_address=current_user.full_address
    )


@router.put("/profile", response_model=UserProfile)
async def update_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update current user's profile.
    
    Allows users to update their own profile information.
    
    Args:
        user_update: Updated user information
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        Updated user profile
    """
    user_repo = UserRepository(db)
    updated_user = user_repo.update(current_user, user_update)
    
    return UserProfile(
        id=str(updated_user.id),
        email=updated_user.email,
        first_name=updated_user.first_name,
        last_name=updated_user.last_name,
        date_of_birth=updated_user.date_of_birth,
        phone_number=updated_user.phone_number,
        role=updated_user.role,
        is_active=updated_user.is_active,
        is_verified=updated_user.is_verified,
        address_line1=updated_user.address_line1,
        address_line2=updated_user.address_line2,
        city=updated_user.city,
        state_province=updated_user.state_province,
        postal_code=updated_user.postal_code,
        country=updated_user.country,
        created_at=updated_user.created_at.isoformat(),
        updated_at=updated_user.updated_at.isoformat(),
        full_name=updated_user.full_name,
        full_address=updated_user.full_address
    )


@router.get("", response_model=List[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0, description="Number of users to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of users to return"),
    role: UserRole = Query(None, description="Filter by user role"),
    is_active: bool = Query(None, description="Filter by active status"),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    List users (admin only).
    
    Returns a paginated list of users. Only accessible by admin users.
    
    Args:
        skip: Number of users to skip for pagination
        limit: Maximum number of users to return
        role: Optional role filter
        is_active: Optional active status filter
        current_user: Currently authenticated admin user
        db: Database session
        
    Returns:
        List of users matching the criteria
    """
    user_repo = UserRepository(db)
    
    # Build filter criteria
    filters = {}
    if role is not None:
        filters["role"] = role
    if is_active is not None:
        filters["is_active"] = is_active
    
    users = user_repo.get_multi(skip=skip, limit=limit, **filters)
    
    return [
        UserResponse(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            date_of_birth=user.date_of_birth,
            phone_number=user.phone_number,
            role=user.role,
            is_active=user.is_active,
            is_verified=user.is_verified,
            address_line1=user.address_line1,
            address_line2=user.address_line2,
            city=user.city,
            state_province=user.state_province,
            postal_code=user.postal_code,
            country=user.country,
            created_at=user.created_at.isoformat(),
            updated_at=user.updated_at.isoformat()
        )
        for user in users
    ]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get user by ID.
    
    Returns user information. Regular users can only access their own
    information, while admin users can access any user.
    
    Args:
        user_id: User ID to retrieve
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        User information
        
    Raises:
        HTTPException: If user not found or access denied
    """
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check permissions: users can only access their own data, admins can access any
    if str(current_user.id) != user_id and not current_user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        date_of_birth=user.date_of_birth,
        phone_number=user.phone_number,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        address_line1=user.address_line1,
        address_line2=user.address_line2,
        city=user.city,
        state_province=user.state_province,
        postal_code=user.postal_code,
        country=user.country,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat()
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserAdminUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Update user (admin only).
    
    Allows admin users to update any user's information, including
    role and status changes.
    
    Args:
        user_id: User ID to update
        user_update: Updated user information
        current_user: Currently authenticated admin user
        db: Database session
        
    Returns:
        Updated user information
        
    Raises:
        HTTPException: If user not found or email already taken
    """
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if email is being changed and if it's already taken
    if user_update.email and user_update.email != user.email:
        if user_repo.is_email_taken(user_update.email, user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    updated_user = user_repo.update(user, user_update)
    
    return UserResponse(
        id=str(updated_user.id),
        email=updated_user.email,
        first_name=updated_user.first_name,
        last_name=updated_user.last_name,
        date_of_birth=updated_user.date_of_birth,
        phone_number=updated_user.phone_number,
        role=updated_user.role,
        is_active=updated_user.is_active,
        is_verified=updated_user.is_verified,
        address_line1=updated_user.address_line1,
        address_line2=updated_user.address_line2,
        city=updated_user.city,
        state_province=updated_user.state_province,
        postal_code=updated_user.postal_code,
        country=updated_user.country,
        created_at=updated_user.created_at.isoformat(),
        updated_at=updated_user.updated_at.isoformat()
    )


@router.post("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Deactivate user account (admin only).
    
    Deactivates a user account, preventing them from logging in.
    
    Args:
        user_id: User ID to deactivate
        current_user: Currently authenticated admin user
        db: Database session
        
    Returns:
        Updated user information
        
    Raises:
        HTTPException: If user not found
    """
    auth_service = AuthService(db)
    user = auth_service.deactivate_user(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        date_of_birth=user.date_of_birth,
        phone_number=user.phone_number,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        address_line1=user.address_line1,
        address_line2=user.address_line2,
        city=user.city,
        state_province=user.state_province,
        postal_code=user.postal_code,
        country=user.country,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat()
    )


@router.post("/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Activate user account (admin only).
    
    Activates a previously deactivated user account.
    
    Args:
        user_id: User ID to activate
        current_user: Currently authenticated admin user
        db: Database session
        
    Returns:
        Updated user information
        
    Raises:
        HTTPException: If user not found
    """
    auth_service = AuthService(db)
    user = auth_service.activate_user(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        date_of_birth=user.date_of_birth,
        phone_number=user.phone_number,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        address_line1=user.address_line1,
        address_line2=user.address_line2,
        city=user.city,
        state_province=user.state_province,
        postal_code=user.postal_code,
        country=user.country,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat()
    )