"""
GDPR compliance service for data export and deletion.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.kyc import Document, KYCCheck
from app.models.user import User
from app.models.webhook import WebhookEvent
from app.repositories.kyc_repository import KYCRepository
from app.repositories.user_repository import UserRepository
from app.repositories.webhook_repository import WebhookRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class GDPRService:
    """Service for GDPR compliance operations."""

    def __init__(
        self,
        db: Session,
        user_repo: UserRepository = None,
        kyc_repo: KYCRepository = None,
        webhook_repo: WebhookRepository = None,
    ):
        self.db = db
        self.user_repo = user_repo or UserRepository(db)
        self.kyc_repo = kyc_repo or KYCRepository(db)
        self.webhook_repo = webhook_repo or WebhookRepository(db)

    async def export_user_data(self, user_id: UUID) -> Dict:
        """
        Export all user data for GDPR compliance.

        Args:
            user_id: UUID of the user

        Returns:
            Dictionary containing all user data

        Raises:
            ValueError: If user not found
        """
        logger.info("Starting GDPR data export", user_id=str(user_id))

        # Get user data
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Export user profile data
        user_data = {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "date_of_birth": (
                user.date_of_birth.isoformat() if user.date_of_birth else None
            ),
            "phone_number": user.phone_number,  # Will be decrypted automatically
            "address": {
                "line1": user.address_line1,
                "line2": user.address_line2,
                "city": user.city,
                "state_province": user.state_province,
                "postal_code": user.postal_code,
                "country": user.country,
            },
            "role": user.role.value,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
        }

        # Export KYC data
        kyc_checks = await self.kyc_repo.get_by_user_id(user_id)
        kyc_data = []

        for kyc_check in kyc_checks:
            # Get documents for this KYC check
            documents = await self.kyc_repo.get_documents_by_kyc_id(kyc_check.id)

            kyc_data.append(
                {
                    "id": str(kyc_check.id),
                    "status": kyc_check.status.value,
                    "provider": kyc_check.provider,
                    "provider_reference": kyc_check.provider_reference,
                    "verification_result": kyc_check.verification_result,
                    "risk_score": kyc_check.risk_score,
                    "submitted_at": kyc_check.submitted_at.isoformat(),
                    "completed_at": (
                        kyc_check.completed_at.isoformat()
                        if kyc_check.completed_at
                        else None
                    ),
                    "expires_at": (
                        kyc_check.expires_at.isoformat()
                        if kyc_check.expires_at
                        else None
                    ),
                    "notes": kyc_check.notes,
                    "rejection_reason": kyc_check.rejection_reason,
                    "documents": [
                        {
                            "id": str(doc.id),
                            "document_type": doc.document_type.value,
                            "file_name": doc.file_name,
                            "file_size": doc.file_size,
                            "document_number": doc.document_number,  # Will be decrypted automatically
                            "issuing_country": doc.issuing_country,
                            "issue_date": (
                                doc.issue_date.isoformat() if doc.issue_date else None
                            ),
                            "expiry_date": (
                                doc.expiry_date.isoformat() if doc.expiry_date else None
                            ),
                            "is_verified": doc.is_verified,
                            "verification_notes": doc.verification_notes,
                            "uploaded_at": doc.created_at.isoformat(),
                        }
                        for doc in documents
                    ],
                }
            )

        # Export webhook events related to user
        webhook_events = await self.webhook_repo.get_by_user_id(user_id)
        webhook_data = [
            {
                "id": str(event.id),
                "provider": event.provider,
                "event_type": event.event_type,
                "processed": event.processed,
                "processed_at": (
                    event.processed_at.isoformat() if event.processed_at else None
                ),
                "retry_count": event.retry_count,
                "created_at": event.created_at.isoformat(),
                # Note: payload and signature are not included for security reasons
            }
            for event in webhook_events
        ]

        export_data = {
            "export_metadata": {
                "user_id": str(user_id),
                "export_date": datetime.utcnow().isoformat(),
                "export_type": "gdpr_data_export",
                "version": "1.0",
            },
            "user_profile": user_data,
            "kyc_checks": kyc_data,
            "webhook_events": webhook_data,
        }

        logger.info(
            "GDPR data export completed",
            user_id=str(user_id),
            kyc_checks_count=len(kyc_data),
            webhook_events_count=len(webhook_data),
        )

        return export_data

    async def delete_user_data(self, user_id: UUID, soft_delete: bool = True) -> Dict:
        """
        Delete user data for GDPR compliance.

        Args:
            user_id: UUID of the user
            soft_delete: If True, mark as deleted but keep for audit. If False, hard delete.

        Returns:
            Dictionary with deletion summary

        Raises:
            ValueError: If user not found
        """
        logger.info(
            "Starting GDPR data deletion", user_id=str(user_id), soft_delete=soft_delete
        )

        # Get user data
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        deletion_summary = {
            "user_id": str(user_id),
            "deletion_date": datetime.utcnow().isoformat(),
            "soft_delete": soft_delete,
            "deleted_items": {
                "user_profile": False,
                "kyc_checks": 0,
                "documents": 0,
                "webhook_events": 0,
            },
        }

        if soft_delete:
            # Soft delete: anonymize sensitive data but keep records for audit
            await self._anonymize_user_data(user)
            deletion_summary["deleted_items"]["user_profile"] = True

            # Anonymize KYC data
            kyc_checks = await self.kyc_repo.get_by_user_id(user_id)
            for kyc_check in kyc_checks:
                await self._anonymize_kyc_data(kyc_check)
                deletion_summary["deleted_items"]["kyc_checks"] += 1

                # Anonymize documents
                documents = await self.kyc_repo.get_documents_by_kyc_id(kyc_check.id)
                for document in documents:
                    await self._anonymize_document_data(document)
                    deletion_summary["deleted_items"]["documents"] += 1
        else:
            # Hard delete: remove all data
            # Delete documents first (due to foreign key constraints)
            kyc_checks = await self.kyc_repo.get_by_user_id(user_id)
            for kyc_check in kyc_checks:
                documents = await self.kyc_repo.get_documents_by_kyc_id(kyc_check.id)
                for document in documents:
                    await self.kyc_repo.delete_document(document.id)
                    deletion_summary["deleted_items"]["documents"] += 1

                # Delete KYC checks
                await self.kyc_repo.delete(kyc_check.id)
                deletion_summary["deleted_items"]["kyc_checks"] += 1

            # Delete webhook events
            webhook_events = await self.webhook_repo.get_by_user_id(user_id)
            for event in webhook_events:
                await self.webhook_repo.delete(event.id)
                deletion_summary["deleted_items"]["webhook_events"] += 1

            # Delete user profile
            await self.user_repo.delete(user_id)
            deletion_summary["deleted_items"]["user_profile"] = True

        # Commit the transaction
        self.db.commit()

        logger.info(
            "GDPR data deletion completed",
            user_id=str(user_id),
            deletion_summary=deletion_summary,
        )

        return deletion_summary

    async def _anonymize_user_data(self, user: User) -> None:
        """Anonymize user data for soft deletion."""
        user.email = f"deleted_user_{user.id}@deleted.local"
        user.first_name = "DELETED"
        user.last_name = "USER"
        user.phone_number = None
        user.date_of_birth = None
        user.address_line1 = None
        user.address_line2 = None
        user.city = None
        user.state_province = None
        user.postal_code = None
        user.country = None
        user.is_active = False

        await self.user_repo.update(user.id, user)

    async def _anonymize_kyc_data(self, kyc_check: KYCCheck) -> None:
        """Anonymize KYC check data for soft deletion."""
        kyc_check.notes = "Data anonymized for GDPR compliance"
        kyc_check.verification_result = {"anonymized": True}
        kyc_check.rejection_reason = None

        await self.kyc_repo.update(kyc_check.id, kyc_check)

    async def _anonymize_document_data(self, document: Document) -> None:
        """Anonymize document data for soft deletion."""
        document.document_number = None
        document.file_name = "anonymized_document"
        document.verification_notes = "Data anonymized for GDPR compliance"

        # Note: In a real implementation, you would also delete the actual file
        # from storage and update the file_path to point to a placeholder

        await self.kyc_repo.update_document(document.id, document)

    async def get_data_processing_info(self, user_id: UUID) -> Dict:
        """
        Get information about data processing for a user.

        Args:
            user_id: UUID of the user

        Returns:
            Dictionary with data processing information
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        kyc_checks = await self.kyc_repo.get_by_user_id(user_id)

        return {
            "user_id": str(user_id),
            "data_categories": {
                "personal_data": {
                    "collected": True,
                    "purpose": "User identification and account management",
                    "legal_basis": "Contract performance",
                    "retention_period": "As long as account is active + 7 years",
                },
                "kyc_data": {
                    "collected": len(kyc_checks) > 0,
                    "purpose": "Identity verification and regulatory compliance",
                    "legal_basis": "Legal obligation (AML/KYC regulations)",
                    "retention_period": "5 years after account closure",
                },
                "technical_data": {
                    "collected": True,
                    "purpose": "Service provision and security",
                    "legal_basis": "Legitimate interest",
                    "retention_period": "2 years",
                },
            },
            "data_sharing": {
                "third_parties": ["KYC verification providers"],
                "purpose": "Identity verification",
                "safeguards": "Data processing agreements, encryption",
            },
            "user_rights": {
                "access": "Request copy of personal data",
                "rectification": "Request correction of inaccurate data",
                "erasure": "Request deletion of personal data",
                "portability": "Request data in machine-readable format",
                "objection": "Object to processing based on legitimate interest",
            },
        }
