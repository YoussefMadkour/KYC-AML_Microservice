"""
KYC verification service with business logic for verification workflows.
"""

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessLogicError, ValidationError
from app.models.kyc import Document, DocumentType, KYCCheck, KYCStatus
from app.models.user import User
from app.repositories.kyc_repository import DocumentRepository, KYCRepository
from app.repositories.user_repository import UserRepository
from app.schemas.kyc import (
    DocumentCreate,
    KYCCheckCreate,
    KYCCheckResponse,
    KYCCheckUpdate,
    KYCStatusUpdate,
)
from app.utils.encryption import encrypt_field
from app.utils.logging import get_logger

logger = get_logger(__name__)


class KYCService:
    """Service for KYC verification workflows."""

    def __init__(self, db: Session):
        """
        Initialize KYC service.

        Args:
            db: Database session
        """
        self.db = db
        self.kyc_repository = KYCRepository(db)
        self.document_repository = DocumentRepository(db)
        self.user_repository = UserRepository(db)

    def create_kyc_check(
        self, user_id: UUID, kyc_data: KYCCheckCreate
    ) -> KYCCheckResponse:
        """
        Create a new KYC verification check.

        Args:
            user_id: User ID
            kyc_data: KYC check creation data

        Returns:
            Created KYC check response

        Raises:
            ValidationError: If validation fails
            BusinessLogicError: If business rules are violated
        """
        logger.info(f"Creating KYC check for user {user_id}")

        # Validate user exists and is active
        user = self.user_repository.get(user_id)
        if not user:
            raise ValidationError("User not found")

        if not user.is_active:
            raise BusinessLogicError("Cannot create KYC check for inactive user")

        # Check if user already has a pending or in-progress check
        existing_check = self._get_active_check(user_id)
        if existing_check:
            raise BusinessLogicError(
                f"User already has an active KYC check with status: {existing_check.status}"
            )

        # Validate documents
        self._validate_documents(kyc_data.documents)

        try:
            # Create KYC check
            kyc_check_data = {
                "user_id": user_id,
                "provider": kyc_data.provider,
                "status": KYCStatus.PENDING,
                "notes": kyc_data.notes,
                "submitted_at": datetime.utcnow(),
            }

            kyc_check = self.kyc_repository.create_from_dict(kyc_check_data)

            # Create associated documents
            documents = []
            for doc_data in kyc_data.documents:
                document = self._create_document(kyc_check.id, doc_data)
                documents.append(document)

            # Log audit trail
            self._log_status_change(
                kyc_check.id,
                None,
                KYCStatus.PENDING,
                f"KYC check created with {len(documents)} documents",
            )

            logger.info(f"Created KYC check {kyc_check.id} for user {user_id}")

            # Return response with documents
            kyc_check.documents = documents
            return self._to_response(kyc_check)

        except Exception as e:
            logger.error(f"Failed to create KYC check for user {user_id}: {str(e)}")
            self.db.rollback()
            raise BusinessLogicError(f"Failed to create KYC check: {str(e)}")

    def get_kyc_check(
        self, kyc_check_id: UUID, user_id: Optional[UUID] = None
    ) -> Optional[KYCCheckResponse]:
        """
        Get KYC check by ID.

        Args:
            kyc_check_id: KYC check ID
            user_id: Optional user ID for authorization check

        Returns:
            KYC check response if found
        """
        kyc_check = self.kyc_repository.get_with_documents(kyc_check_id)
        if not kyc_check:
            return None

        # Check user authorization if provided
        if user_id and kyc_check.user_id != user_id:
            return None

        return self._to_response(kyc_check)

    def get_user_kyc_checks(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
        status: Optional[KYCStatus] = None,
    ) -> List[KYCCheckResponse]:
        """
        Get KYC checks for a user.

        Args:
            user_id: User ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Optional status filter

        Returns:
            List of KYC check responses
        """
        kyc_checks = self.kyc_repository.get_by_user_id(user_id, skip, limit, status)
        return [self._to_response(check) for check in kyc_checks]

    def update_kyc_status(
        self,
        kyc_check_id: UUID,
        status_update: KYCStatusUpdate,
        updated_by: Optional[str] = None,
    ) -> Optional[KYCCheckResponse]:
        """
        Update KYC check status with validation.

        Args:
            kyc_check_id: KYC check ID
            status_update: Status update data
            updated_by: User who made the update

        Returns:
            Updated KYC check response if found

        Raises:
            ValidationError: If status transition is invalid
            BusinessLogicError: If business rules are violated
        """
        logger.info(
            f"Updating KYC check {kyc_check_id} status to {status_update.status}"
        )

        kyc_check = self.kyc_repository.get(kyc_check_id)
        if not kyc_check:
            return None

        # Validate status transition
        if not kyc_check.can_transition_to(status_update.status):
            raise ValidationError(
                f"Invalid status transition from {kyc_check.status} to {status_update.status}"
            )

        # Store previous status for audit
        previous_status = kyc_check.status

        try:
            # Update status
            updated_check = self.kyc_repository.update_status(
                kyc_check_id=kyc_check_id,
                new_status=status_update.status,
                notes=status_update.notes,
                rejection_reason=status_update.rejection_reason,
            )

            if updated_check:
                # Log audit trail
                self._log_status_change(
                    kyc_check_id,
                    previous_status,
                    status_update.status,
                    status_update.notes
                    or f"Status updated by {updated_by or 'system'}",
                    updated_by,
                )

                logger.info(
                    f"Updated KYC check {kyc_check_id} status from {previous_status} to {status_update.status}"
                )

                return self._to_response(updated_check)

        except Exception as e:
            logger.error(f"Failed to update KYC check {kyc_check_id}: {str(e)}")
            raise BusinessLogicError(f"Failed to update KYC status: {str(e)}")

        return None

    def update_kyc_check(
        self,
        kyc_check_id: UUID,
        update_data: KYCCheckUpdate,
        updated_by: Optional[str] = None,
    ) -> Optional[KYCCheckResponse]:
        """
        Update KYC check with comprehensive data.

        Args:
            kyc_check_id: KYC check ID
            update_data: Update data
            updated_by: User who made the update

        Returns:
            Updated KYC check response if found
        """
        logger.info(f"Updating KYC check {kyc_check_id}")

        kyc_check = self.kyc_repository.get(kyc_check_id)
        if not kyc_check:
            return None

        # Store previous status for audit if status is being changed
        previous_status = kyc_check.status
        status_changed = update_data.status and update_data.status != previous_status

        # Validate status transition if status is being changed
        if status_changed and not kyc_check.can_transition_to(update_data.status):
            raise ValidationError(
                f"Invalid status transition from {kyc_check.status} to {update_data.status}"
            )

        try:
            # Update using repository method
            updated_check = self.kyc_repository.update_status(
                kyc_check_id=kyc_check_id,
                new_status=update_data.status or kyc_check.status,
                provider_reference=update_data.provider_reference,
                verification_result=update_data.verification_result,
                risk_score=update_data.risk_score,
                notes=update_data.notes,
                rejection_reason=update_data.rejection_reason,
            )

            if updated_check and status_changed:
                # Log audit trail for status change
                self._log_status_change(
                    kyc_check_id,
                    previous_status,
                    update_data.status,
                    update_data.notes or f"Status updated by {updated_by or 'system'}",
                    updated_by,
                )

            logger.info(f"Updated KYC check {kyc_check_id}")
            return self._to_response(updated_check) if updated_check else None

        except Exception as e:
            logger.error(f"Failed to update KYC check {kyc_check_id}: {str(e)}")
            raise BusinessLogicError(f"Failed to update KYC check: {str(e)}")

    def get_kyc_history(self, kyc_check_id: UUID) -> List[Dict]:
        """
        Get KYC check history/audit trail.

        Args:
            kyc_check_id: KYC check ID

        Returns:
            List of history entries
        """
        # This would typically query an audit/history table
        # For now, return basic info from the check itself
        kyc_check = self.kyc_repository.get(kyc_check_id)
        if not kyc_check:
            return []

        history = [
            {
                "id": str(uuid4()),
                "kyc_check_id": str(kyc_check_id),
                "previous_status": None,
                "new_status": KYCStatus.PENDING,
                "timestamp": kyc_check.created_at.isoformat(),
                "notes": "KYC check created",
                "changed_by": "system",
            }
        ]

        if kyc_check.completed_at:
            history.append(
                {
                    "id": str(uuid4()),
                    "kyc_check_id": str(kyc_check_id),
                    "previous_status": KYCStatus.IN_PROGRESS,
                    "new_status": kyc_check.status,
                    "timestamp": kyc_check.completed_at.isoformat(),
                    "notes": kyc_check.notes or f"Status changed to {kyc_check.status}",
                    "changed_by": "system",
                }
            )

        return history

    def get_pending_checks(self, limit: int = 100) -> List[KYCCheckResponse]:
        """
        Get pending KYC checks for processing.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of pending KYC checks
        """
        pending_checks = self.kyc_repository.get_pending_checks(limit)
        return [self._to_response(check) for check in pending_checks]

    def get_kyc_statistics(self) -> Dict:
        """
        Get KYC verification statistics.

        Returns:
            Dictionary with statistics
        """
        return self.kyc_repository.get_statistics()

    def _get_active_check(self, user_id: UUID) -> Optional[KYCCheck]:
        """
        Get user's active (non-final) KYC check.

        Args:
            user_id: User ID

        Returns:
            Active KYC check if found
        """
        active_statuses = [
            KYCStatus.PENDING,
            KYCStatus.IN_PROGRESS,
            KYCStatus.MANUAL_REVIEW,
        ]

        for status in active_statuses:
            checks = self.kyc_repository.get_by_user_id(user_id, limit=1, status=status)
            if checks:
                return checks[0]

        return None

    def _validate_documents(self, documents: List[DocumentCreate]) -> None:
        """
        Validate document requirements.

        Args:
            documents: List of documents to validate

        Raises:
            ValidationError: If validation fails
        """
        if not documents:
            raise ValidationError("At least one document is required")

        # Check for required document types
        document_types = {doc.document_type for doc in documents}

        # At least one identity document is required
        identity_types = {
            DocumentType.PASSPORT,
            DocumentType.DRIVER_LICENSE,
            DocumentType.NATIONAL_ID,
        }
        if not document_types.intersection(identity_types):
            raise ValidationError(
                "At least one identity document (passport, "
                "driver license, or national ID) is required"
            )

        # Check for duplicate document types
        if len(document_types) != len(documents):
            raise ValidationError("Duplicate document types are not allowed")

        # Validate individual documents
        for doc in documents:
            self._validate_document(doc)

    def _validate_document(self, document: DocumentCreate) -> None:
        """
        Validate individual document.

        Args:
            document: Document to validate

        Raises:
            ValidationError: If validation fails
        """
        # Validate file hash format
        if len(document.file_hash) != 64:
            raise ValidationError(
                "File hash must be a valid SHA-256 hash (64 characters)"
            )

        # Validate expiry date for documents that should have one
        expiry_required_types = {
            DocumentType.PASSPORT,
            DocumentType.DRIVER_LICENSE,
            DocumentType.NATIONAL_ID,
        }
        if document.document_type in expiry_required_types and not document.expiry_date:
            raise ValidationError(
                f"{document.document_type.value} must have an expiry date"
            )

        # Check if document is not expired
        if document.expiry_date and document.expiry_date < datetime.utcnow():
            raise ValidationError(f"{document.document_type.value} is expired")

    def _create_document(
        self, kyc_check_id: UUID, doc_data: DocumentCreate
    ) -> Document:
        """
        Create a document with encryption.

        Args:
            kyc_check_id: KYC check ID
            doc_data: Document creation data

        Returns:
            Created document
        """
        # Encrypt sensitive document number if provided
        encrypted_doc_number = None
        if doc_data.document_number:
            encrypted_doc_number = encrypt_field(doc_data.document_number)

        document_dict = {
            "kyc_check_id": kyc_check_id,
            "document_type": doc_data.document_type,
            "file_path": doc_data.file_path,
            "file_name": doc_data.file_name,
            "file_size": doc_data.file_size,
            "file_hash": doc_data.file_hash,
            "mime_type": doc_data.mime_type,
            "document_number": encrypted_doc_number,
            "issuing_country": doc_data.issuing_country,
            "issue_date": doc_data.issue_date,
            "expiry_date": doc_data.expiry_date,
            "is_verified": "pending",
        }

        return self.document_repository.create_from_dict(document_dict)

    def _log_status_change(
        self,
        kyc_check_id: UUID,
        previous_status: Optional[KYCStatus],
        new_status: KYCStatus,
        notes: str,
        changed_by: Optional[str] = None,
    ) -> None:
        """
        Log KYC status change for audit trail.

        Args:
            kyc_check_id: KYC check ID
            previous_status: Previous status
            new_status: New status
            notes: Change notes
            changed_by: User who made the change
        """
        logger.info(
            "KYC status change",
            extra={
                "kyc_check_id": str(kyc_check_id),
                "previous_status": previous_status.value if previous_status else None,
                "new_status": new_status.value,
                "notes": notes,
                "changed_by": changed_by or "system",
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    def _to_response(self, kyc_check: KYCCheck) -> KYCCheckResponse:
        """
        Convert KYC check model to response schema.

        Args:
            kyc_check: KYC check model

        Returns:
            KYC check response schema
        """
        # Convert the model to a dictionary with proper type conversions
        data = {
            "id": str(kyc_check.id),
            "user_id": str(kyc_check.user_id),
            "provider": kyc_check.provider,
            "status": kyc_check.status,
            "provider_reference": kyc_check.provider_reference,
            "verification_result": kyc_check.verification_result,
            "risk_score": kyc_check.risk_score,
            "submitted_at": (
                kyc_check.submitted_at.isoformat() if kyc_check.submitted_at else None
            ),
            "completed_at": (
                kyc_check.completed_at.isoformat() if kyc_check.completed_at else None
            ),
            "expires_at": (
                kyc_check.expires_at.isoformat() if kyc_check.expires_at else None
            ),
            "notes": kyc_check.notes,
            "rejection_reason": kyc_check.rejection_reason,
            "is_completed": kyc_check.is_completed,
            "is_pending_review": kyc_check.is_pending_review,
            "processing_time_seconds": kyc_check.processing_time_seconds,
            "created_at": kyc_check.created_at.isoformat(),
            "updated_at": kyc_check.updated_at.isoformat(),
            "documents": [],
        }

        # Convert documents if they exist
        if hasattr(kyc_check, "documents") and kyc_check.documents:
            data["documents"] = [
                {
                    "id": str(doc.id),
                    "kyc_check_id": str(doc.kyc_check_id),
                    "document_type": doc.document_type,
                    "file_name": doc.file_name,
                    "document_number": doc.document_number,
                    "issuing_country": doc.issuing_country,
                    "issue_date": (
                        doc.issue_date.isoformat() if doc.issue_date else None
                    ),
                    "expiry_date": (
                        doc.expiry_date.isoformat() if doc.expiry_date else None
                    ),
                    "file_size": doc.file_size,
                    "file_hash": doc.file_hash,
                    "mime_type": doc.mime_type,
                    "is_verified": doc.is_verified,
                    "verification_notes": doc.verification_notes,
                    "is_expired": doc.is_expired,
                    "days_until_expiry": doc.days_until_expiry,
                    "created_at": doc.created_at.isoformat(),
                    "updated_at": doc.updated_at.isoformat(),
                }
                for doc in kyc_check.documents
            ]

        return KYCCheckResponse(**data)
