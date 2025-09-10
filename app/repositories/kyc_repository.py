"""
KYC repository for data access operations.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session, joinedload

from app.models.kyc import Document, DocumentType, KYCCheck, KYCStatus
from app.repositories.base import BaseRepository
from app.schemas.kyc import DocumentCreate, KYCCheckCreate, KYCCheckUpdate


class KYCRepository(BaseRepository[KYCCheck, KYCCheckCreate, KYCCheckUpdate]):
    """Repository for KYC check operations."""

    def __init__(self, db: Session):
        """Initialize KYC repository."""
        super().__init__(KYCCheck, db)

    async def get_by_user_id(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
        status: Optional[KYCStatus] = None,
    ) -> List[KYCCheck]:
        """
        Get KYC checks for a specific user.

        Args:
            user_id: User ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Optional status filter

        Returns:
            List of KYC checks
        """
        query = (
            self.db.query(KYCCheck)
            .options(joinedload(KYCCheck.documents))
            .filter(KYCCheck.user_id == user_id)
        )

        if status:
            query = query.filter(KYCCheck.status == status)

        return query.order_by(desc(KYCCheck.created_at)).offset(skip).limit(limit).all()

    def get_with_documents(self, kyc_check_id: UUID) -> Optional[KYCCheck]:
        """
        Get KYC check with associated documents.

        Args:
            kyc_check_id: KYC check ID

        Returns:
            KYC check with documents if found
        """
        return (
            self.db.query(KYCCheck)
            .options(joinedload(KYCCheck.documents))
            .filter(KYCCheck.id == kyc_check_id)
            .first()
        )

    def get_by_provider_reference(self, provider_reference: str) -> Optional[KYCCheck]:
        """
        Get KYC check by provider reference.

        Args:
            provider_reference: Provider reference ID

        Returns:
            KYC check if found
        """
        return (
            self.db.query(KYCCheck)
            .filter(KYCCheck.provider_reference == provider_reference)
            .first()
        )

    def get_pending_checks(self, limit: int = 100) -> List[KYCCheck]:
        """
        Get pending KYC checks for processing.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of pending KYC checks
        """
        return (
            self.db.query(KYCCheck)
            .filter(KYCCheck.status == KYCStatus.PENDING)
            .order_by(KYCCheck.created_at)
            .limit(limit)
            .all()
        )

    def get_checks_by_status(
        self, status: KYCStatus, skip: int = 0, limit: int = 100
    ) -> List[KYCCheck]:
        """
        Get KYC checks by status.

        Args:
            status: KYC status to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of KYC checks
        """
        return (
            self.db.query(KYCCheck)
            .filter(KYCCheck.status == status)
            .order_by(desc(KYCCheck.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_by_user_id(
        self, user_id: UUID, status: Optional[KYCStatus] = None
    ) -> int:
        """
        Count KYC checks for a user.

        Args:
            user_id: User ID
            status: Optional status filter

        Returns:
            Number of KYC checks
        """
        query = self.db.query(KYCCheck).filter(KYCCheck.user_id == user_id)

        if status:
            query = query.filter(KYCCheck.status == status)

        return query.count()

    def get_user_latest_check(self, user_id: UUID) -> Optional[KYCCheck]:
        """
        Get user's latest KYC check.

        Args:
            user_id: User ID

        Returns:
            Latest KYC check if found
        """
        return (
            self.db.query(KYCCheck)
            .filter(KYCCheck.user_id == user_id)
            .order_by(desc(KYCCheck.created_at))
            .first()
        )

    def update_status(
        self,
        kyc_check_id: UUID,
        new_status: KYCStatus,
        provider_reference: Optional[str] = None,
        verification_result: Optional[dict] = None,
        risk_score: Optional[str] = None,
        notes: Optional[str] = None,
        rejection_reason: Optional[str] = None,
    ) -> Optional[KYCCheck]:
        """
        Update KYC check status and related fields.

        Args:
            kyc_check_id: KYC check ID
            new_status: New status
            provider_reference: Provider reference ID
            verification_result: Verification results
            risk_score: Risk assessment score
            notes: Additional notes
            rejection_reason: Rejection reason if applicable

        Returns:
            Updated KYC check if found
        """
        kyc_check = self.get(kyc_check_id)
        if not kyc_check:
            return None

        # Validate status transition
        if not kyc_check.can_transition_to(new_status):
            raise ValueError(
                f"Invalid status transition from {kyc_check.status} to {new_status}"
            )

        # Update fields
        kyc_check.status = new_status

        if provider_reference:
            kyc_check.provider_reference = provider_reference

        if verification_result:
            kyc_check.verification_result = verification_result

        if risk_score:
            kyc_check.risk_score = risk_score

        if notes:
            kyc_check.notes = notes

        if rejection_reason:
            kyc_check.rejection_reason = rejection_reason

        # Set completion timestamp for final states
        if new_status in [KYCStatus.APPROVED, KYCStatus.REJECTED]:
            kyc_check.completed_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(kyc_check)
        return kyc_check

    def get_statistics(self) -> dict:
        """
        Get KYC check statistics.

        Returns:
            Dictionary with statistics
        """
        total = self.db.query(KYCCheck).count()

        status_counts = (
            self.db.query(KYCCheck.status, func.count(KYCCheck.id))
            .group_by(KYCCheck.status)
            .all()
        )

        status_stats = {status.value: 0 for status in KYCStatus}
        for status, count in status_counts:
            status_stats[status.value] = count

        return {
            "total": total,
            "by_status": status_stats,
            "completion_rate": (
                (status_stats["approved"] + status_stats["rejected"]) / total * 100
                if total > 0
                else 0
            ),
        }


class DocumentRepository(BaseRepository[Document, DocumentCreate, dict]):
    """Repository for document operations."""

    def __init__(self, db: Session):
        """Initialize document repository."""
        super().__init__(Document, db)

    def get_by_kyc_check_id(self, kyc_check_id: UUID) -> List[Document]:
        """
        Get documents for a KYC check.

        Args:
            kyc_check_id: KYC check ID

        Returns:
            List of documents
        """
        return (
            self.db.query(Document)
            .filter(Document.kyc_check_id == kyc_check_id)
            .order_by(Document.created_at)
            .all()
        )

    def get_by_type_and_check(
        self, kyc_check_id: UUID, document_type: DocumentType
    ) -> Optional[Document]:
        """
        Get document by type for a specific KYC check.

        Args:
            kyc_check_id: KYC check ID
            document_type: Document type

        Returns:
            Document if found
        """
        return (
            self.db.query(Document)
            .filter(
                and_(
                    Document.kyc_check_id == kyc_check_id,
                    Document.document_type == document_type,
                )
            )
            .first()
        )

    def get_expired_documents(self, limit: int = 100) -> List[Document]:
        """
        Get expired documents.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of expired documents
        """
        return (
            self.db.query(Document)
            .filter(Document.expiry_date < datetime.utcnow())
            .limit(limit)
            .all()
        )

    def update_verification_status(
        self,
        document_id: UUID,
        is_verified: str,
        verification_notes: Optional[str] = None,
    ) -> Optional[Document]:
        """
        Update document verification status.

        Args:
            document_id: Document ID
            is_verified: Verification status
            verification_notes: Verification notes

        Returns:
            Updated document if found
        """
        document = self.get(document_id)
        if not document:
            return None

        document.is_verified = is_verified
        if verification_notes:
            document.verification_notes = verification_notes

        self.db.commit()
        self.db.refresh(document)
        return document

    async def get_documents_by_kyc_id(self, kyc_check_id: UUID) -> List[Document]:
        """
        Get all documents for a KYC check (alias for get_by_kyc_check_id).

        Args:
            kyc_check_id: KYC check ID

        Returns:
            List of documents
        """
        return self.get_by_kyc_check_id(kyc_check_id)

    async def delete_document(self, document_id: UUID) -> bool:
        """
        Delete a document.

        Args:
            document_id: Document ID

        Returns:
            True if deleted, False if not found
        """
        return self.delete(document_id)

    async def update_document(
        self, document_id: UUID, document: Document
    ) -> Optional[Document]:
        """
        Update a document.

        Args:
            document_id: Document ID
            document: Updated document data

        Returns:
            Updated document if found
        """
        existing_document = self.get(document_id)
        if not existing_document:
            return None

        # Update fields
        for key, value in document.__dict__.items():
            if not key.startswith("_") and hasattr(existing_document, key):
                setattr(existing_document, key, value)

        self.db.commit()
        self.db.refresh(existing_document)
        return existing_document
