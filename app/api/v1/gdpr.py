"""
GDPR compliance API endpoints for data export and deletion.
"""

from typing import Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_admin_or_self
from app.models.user import User
from app.services.gdpr_service import GDPRService
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/gdpr", tags=["GDPR Compliance"])


@router.get("/export/{user_id}", response_model=Dict)
async def export_user_data(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """
    Export all user data for GDPR compliance.

    Users can export their own data, admins can export any user's data.
    """
    # Check authorization
    require_admin_or_self(current_user, user_id)

    try:
        gdpr_service = GDPRService(db)
        export_data = await gdpr_service.export_user_data(user_id)

        logger.info(
            "GDPR data export requested",
            user_id=str(user_id),
            requested_by=str(current_user.id),
        )

        return export_data

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("GDPR data export failed", user_id=str(user_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export user data",
        )


@router.get("/export/me", response_model=Dict)
async def export_my_data(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Dict:
    """
    Export current user's data for GDPR compliance.
    """
    try:
        gdpr_service = GDPRService(db)
        export_data = await gdpr_service.export_user_data(current_user.id)

        logger.info("GDPR self data export requested", user_id=str(current_user.id))

        return export_data

    except Exception as e:
        logger.error(
            "GDPR self data export failed", user_id=str(current_user.id), error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export your data",
        )


@router.delete("/delete/{user_id}", response_model=Dict)
async def delete_user_data(
    user_id: UUID,
    soft_delete: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """
    Delete user data for GDPR compliance.

    Args:
        user_id: UUID of the user to delete
        soft_delete: If True, anonymize data but keep for audit. If False, hard delete.

    Only admins can delete user data.
    """
    if not current_user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete user data",
        )

    try:
        gdpr_service = GDPRService(db)
        deletion_summary = await gdpr_service.delete_user_data(user_id, soft_delete)

        logger.info(
            "GDPR data deletion requested",
            user_id=str(user_id),
            requested_by=str(current_user.id),
            soft_delete=soft_delete,
        )

        return deletion_summary

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("GDPR data deletion failed", user_id=str(user_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user data",
        )


@router.delete("/delete/me", response_model=Dict)
async def delete_my_data(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Dict:
    """
    Delete current user's own data (soft delete only for self-service).
    """
    try:
        gdpr_service = GDPRService(db)
        deletion_summary = await gdpr_service.delete_user_data(
            current_user.id, soft_delete=True
        )

        logger.info("GDPR self data deletion requested", user_id=str(current_user.id))

        return deletion_summary

    except Exception as e:
        logger.error(
            "GDPR self data deletion failed", user_id=str(current_user.id), error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete your data",
        )


@router.get("/processing-info/{user_id}", response_model=Dict)
async def get_data_processing_info(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """
    Get information about data processing for a user.

    Users can get their own processing info, admins can get any user's info.
    """
    # Check authorization
    require_admin_or_self(current_user, user_id)

    try:
        gdpr_service = GDPRService(db)
        processing_info = await gdpr_service.get_data_processing_info(user_id)

        return processing_info

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(
            "Failed to get data processing info", user_id=str(user_id), error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get data processing information",
        )


@router.get("/processing-info/me", response_model=Dict)
async def get_my_data_processing_info(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Dict:
    """
    Get data processing information for current user.
    """
    try:
        gdpr_service = GDPRService(db)
        processing_info = await gdpr_service.get_data_processing_info(current_user.id)

        return processing_info

    except Exception as e:
        logger.error(
            "Failed to get self data processing info",
            user_id=str(current_user.id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get your data processing information",
        )
