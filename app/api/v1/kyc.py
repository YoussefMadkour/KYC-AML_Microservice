"""
KYC verification API endpoints.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_active_user,
    get_current_admin_user,
    get_current_compliance_user,
    get_db
)
from app.core.exceptions import BusinessLogicError, ValidationError
from app.models.kyc import KYCStatus
from app.models.user import User
from app.schemas.kyc import (
    KYCCheckCreate,
    KYCCheckResponse,
    KYCCheckListResponse,
    KYCCheckUpdate,
    KYCStatusUpdate,
    KYCHistoryResponse
)
from app.services.kyc_service import KYCService


router = APIRouter()


@router.post("/checks", response_model=KYCCheckResponse, status_code=status.HTTP_201_CREATED)
async def create_kyc_check(
    kyc_data: KYCCheckCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Initiate KYC verification for the current user.
    
    Creates a new KYC verification check with the provided documents
    and initiates the verification process.
    
    Args:
        kyc_data: KYC check creation data including documents
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        Created KYC check with tracking ID
        
    Raises:
        HTTPException: If validation fails or user already has active check
    """
    try:
        kyc_service = KYCService(db)
        kyc_check = kyc_service.create_kyc_check(current_user.id, kyc_data)
        return kyc_check
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.get("/checks/{check_id}", response_model=KYCCheckResponse)
async def get_kyc_check(
    check_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get KYC check status by ID.
    
    Returns the current status and details of a KYC verification check.
    Regular users can only access their own checks, while admin/compliance
    users can access any check.
    
    Args:
        check_id: KYC check ID
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        KYC check details and current status
        
    Raises:
        HTTPException: If check not found or access denied
    """
    try:
        check_uuid = UUID(check_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid check ID format"
        )
    
    kyc_service = KYCService(db)
    
    # Admin and compliance users can access any check
    if current_user.is_admin() or current_user.is_compliance_officer():
        kyc_check = kyc_service.get_kyc_check(check_uuid)
    else:
        # Regular users can only access their own checks
        kyc_check = kyc_service.get_kyc_check(check_uuid, current_user.id)
    
    if not kyc_check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC check not found"
        )
    
    return kyc_check


@router.get("/checks", response_model=KYCCheckListResponse)
async def list_kyc_checks(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    status_filter: Optional[KYCStatus] = Query(None, alias="status", description="Filter by KYC status"),
    user_id: Optional[str] = Query(None, description="Filter by user ID (admin/compliance only)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List KYC checks with pagination and filtering.
    
    Returns a paginated list of KYC checks. Regular users see only their own
    checks, while admin/compliance users can see all checks and filter by user.
    
    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        status_filter: Optional status filter
        user_id: Optional user ID filter (admin/compliance only)
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        Paginated list of KYC checks
        
    Raises:
        HTTPException: If user_id filter used without proper permissions
    """
    kyc_service = KYCService(db)
    
    # Determine which user's checks to retrieve
    target_user_id = current_user.id
    
    # Admin and compliance users can filter by user_id
    if user_id:
        if not (current_user.is_admin() or current_user.is_compliance_officer()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to filter by user ID"
            )
        try:
            target_user_id = UUID(user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format"
            )
    
    # Get KYC checks
    kyc_checks = kyc_service.get_user_kyc_checks(
        target_user_id, 
        skip=skip, 
        limit=limit,
        status=status_filter
    )
    
    # Get total count for pagination
    # Note: This is a simplified implementation. In production, you'd want
    # to implement a more efficient count query in the repository
    total_checks = kyc_service.get_user_kyc_checks(target_user_id, status=status_filter)
    total = len(total_checks)
    
    # Calculate pagination info
    pages = (total + limit - 1) // limit if total > 0 else 0
    current_page = (skip // limit) + 1
    
    return KYCCheckListResponse(
        items=kyc_checks,
        total=total,
        page=current_page,
        size=limit,
        pages=pages
    )


@router.put("/checks/{check_id}", response_model=KYCCheckResponse)
async def update_kyc_check(
    check_id: str,
    update_data: KYCCheckUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Update KYC check (admin only).
    
    Allows admin users to update KYC check details including status,
    verification results, and notes. This is typically used for manual
    review processes and administrative corrections.
    
    Args:
        check_id: KYC check ID to update
        update_data: Updated KYC check data
        current_user: Currently authenticated admin user
        db: Database session
        
    Returns:
        Updated KYC check
        
    Raises:
        HTTPException: If check not found or update fails
    """
    try:
        check_uuid = UUID(check_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid check ID format"
        )
    
    try:
        kyc_service = KYCService(db)
        updated_check = kyc_service.update_kyc_check(
            check_uuid, 
            update_data,
            updated_by=current_user.email
        )
        
        if not updated_check:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="KYC check not found"
            )
        
        return updated_check
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.patch("/checks/{check_id}/status", response_model=KYCCheckResponse)
async def update_kyc_status(
    check_id: str,
    status_update: KYCStatusUpdate,
    current_user: User = Depends(get_current_compliance_user),
    db: Session = Depends(get_db)
):
    """
    Update KYC check status (compliance/admin only).
    
    Allows compliance officers and admin users to update the status
    of a KYC check. This is typically used for manual review decisions.
    
    Args:
        check_id: KYC check ID to update
        status_update: New status and optional notes
        current_user: Currently authenticated compliance/admin user
        db: Database session
        
    Returns:
        Updated KYC check
        
    Raises:
        HTTPException: If check not found or status transition invalid
    """
    try:
        check_uuid = UUID(check_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid check ID format"
        )
    
    try:
        kyc_service = KYCService(db)
        updated_check = kyc_service.update_kyc_status(
            check_uuid,
            status_update,
            updated_by=current_user.email
        )
        
        if not updated_check:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="KYC check not found"
            )
        
        return updated_check
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.get("/checks/{check_id}/history", response_model=KYCHistoryResponse)
async def get_kyc_history(
    check_id: str,
    current_user: User = Depends(get_current_compliance_user),
    db: Session = Depends(get_db)
):
    """
    Get KYC check history/audit trail (compliance/admin only).
    
    Returns the complete audit trail for a KYC check, including all
    status changes and modifications.
    
    Args:
        check_id: KYC check ID
        current_user: Currently authenticated compliance/admin user
        db: Database session
        
    Returns:
        KYC check history and audit trail
        
    Raises:
        HTTPException: If check not found
    """
    try:
        check_uuid = UUID(check_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid check ID format"
        )
    
    kyc_service = KYCService(db)
    
    # Verify check exists
    kyc_check = kyc_service.get_kyc_check(check_uuid)
    if not kyc_check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC check not found"
        )
    
    # Get history
    history = kyc_service.get_kyc_history(check_uuid)
    
    return KYCHistoryResponse(
        kyc_check_id=check_id,
        history=history,
        total_entries=len(history)
    )


@router.get("/statistics")
async def get_kyc_statistics(
    current_user: User = Depends(get_current_compliance_user),
    db: Session = Depends(get_db)
):
    """
    Get KYC verification statistics (compliance/admin only).
    
    Returns aggregated statistics about KYC verifications including
    status distribution and completion rates.
    
    Args:
        current_user: Currently authenticated compliance/admin user
        db: Database session
        
    Returns:
        KYC verification statistics
    """
    kyc_service = KYCService(db)
    statistics = kyc_service.get_kyc_statistics()
    
    return {
        "statistics": statistics,
        "generated_at": "2024-01-01T00:00:00Z",  # This would be current timestamp
        "generated_by": current_user.email
    }


@router.get("/pending")
async def get_pending_checks(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    current_user: User = Depends(get_current_compliance_user),
    db: Session = Depends(get_db)
):
    """
    Get pending KYC checks for review (compliance/admin only).
    
    Returns KYC checks that are pending review or processing.
    This is typically used by compliance officers to manage their
    review queue.
    
    Args:
        limit: Maximum number of records to return
        current_user: Currently authenticated compliance/admin user
        db: Database session
        
    Returns:
        List of pending KYC checks
    """
    kyc_service = KYCService(db)
    pending_checks = kyc_service.get_pending_checks(limit)
    
    return {
        "pending_checks": pending_checks,
        "total_pending": len(pending_checks),
        "retrieved_at": "2024-01-01T00:00:00Z"  # This would be current timestamp
    }