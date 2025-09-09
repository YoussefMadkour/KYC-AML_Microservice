"""
KYC Check and Document models with status tracking and relationships.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Column, DateTime, Enum as SQLEnum, ForeignKey, JSON, String, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class KYCStatus(str, Enum):
    """KYC verification status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"
    EXPIRED = "expired"


class DocumentType(str, Enum):
    """Document type enumeration."""
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"
    NATIONAL_ID = "national_id"
    UTILITY_BILL = "utility_bill"
    BANK_STATEMENT = "bank_statement"
    PROOF_OF_ADDRESS = "proof_of_address"


class KYCCheck(BaseModel):
    """KYC verification check model."""
    
    __tablename__ = "kyc_checks"
    
    # Foreign key to user
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to the user being verified"
    )
    
    # Status tracking
    status = Column(
        SQLEnum(KYCStatus),
        default=KYCStatus.PENDING,
        nullable=False,
        index=True,
        doc="Current verification status"
    )
    
    # Provider information
    provider = Column(
        String(100),
        nullable=False,
        doc="KYC provider name (e.g., 'mock_provider_1')"
    )
    
    provider_reference = Column(
        String(255),
        nullable=True,
        index=True,
        doc="External provider's reference ID"
    )
    
    # Verification details
    verification_result = Column(
        JSON,
        nullable=True,
        doc="Detailed verification results from provider"
    )
    
    risk_score = Column(
        String(20),
        nullable=True,
        doc="Risk assessment score (low, medium, high)"
    )
    
    # Timestamps
    submitted_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        doc="When the KYC check was submitted"
    )
    
    completed_at = Column(
        DateTime,
        nullable=True,
        doc="When the KYC check was completed"
    )
    
    expires_at = Column(
        DateTime,
        nullable=True,
        doc="When the KYC verification expires"
    )
    
    # Additional information
    notes = Column(
        Text,
        nullable=True,
        doc="Additional notes or comments"
    )
    
    rejection_reason = Column(
        String(500),
        nullable=True,
        doc="Reason for rejection if status is rejected"
    )
    
    # Relationships
    user = relationship(
        "User",
        back_populates="kyc_checks",
        doc="User associated with this KYC check"
    )
    
    documents = relationship(
        "Document",
        back_populates="kyc_check",
        cascade="all, delete-orphan",
        doc="Documents associated with this KYC check"
    )
    
    def __repr__(self) -> str:
        """String representation of the KYC check."""
        return f"<KYCCheck(id={self.id}, user_id={self.user_id}, status={self.status})>"
    
    @property
    def is_completed(self) -> bool:
        """Check if the KYC verification is completed."""
        return self.status in [
            KYCStatus.APPROVED,
            KYCStatus.REJECTED,
            KYCStatus.EXPIRED
        ]
    
    @property
    def is_pending_review(self) -> bool:
        """Check if the KYC check needs manual review."""
        return self.status == KYCStatus.MANUAL_REVIEW
    
    @property
    def processing_time_seconds(self) -> Optional[int]:
        """Get processing time in seconds if completed."""
        if self.completed_at and self.submitted_at:
            delta = self.completed_at - self.submitted_at
            return int(delta.total_seconds())
        return None
    
    def can_transition_to(self, new_status: KYCStatus) -> bool:
        """Check if status can transition to new status."""
        valid_transitions = {
            KYCStatus.PENDING: [KYCStatus.IN_PROGRESS, KYCStatus.REJECTED],
            KYCStatus.IN_PROGRESS: [
                KYCStatus.APPROVED,
                KYCStatus.REJECTED,
                KYCStatus.MANUAL_REVIEW
            ],
            KYCStatus.MANUAL_REVIEW: [KYCStatus.APPROVED, KYCStatus.REJECTED],
            KYCStatus.APPROVED: [KYCStatus.EXPIRED],
            KYCStatus.REJECTED: [],  # Final state
            KYCStatus.EXPIRED: []    # Final state
        }
        
        return new_status in valid_transitions.get(self.status, [])
    
    def update_status(self, new_status: KYCStatus, notes: Optional[str] = None) -> bool:
        """Update status with validation."""
        if not self.can_transition_to(new_status):
            return False
        
        self.status = new_status
        if notes:
            self.notes = notes
        
        # Set completion timestamp for final states
        if new_status in [KYCStatus.APPROVED, KYCStatus.REJECTED]:
            self.completed_at = datetime.utcnow()
        
        return True


class Document(BaseModel):
    """Document model for KYC verification."""
    
    __tablename__ = "documents"
    
    # Foreign key to KYC check
    kyc_check_id = Column(
        UUID(as_uuid=True),
        ForeignKey("kyc_checks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to the KYC check"
    )
    
    # Document information
    document_type = Column(
        SQLEnum(DocumentType),
        nullable=False,
        doc="Type of document"
    )
    
    # File information
    file_path = Column(
        String(500),
        nullable=False,
        doc="Path to the stored document file"
    )
    
    file_name = Column(
        String(255),
        nullable=False,
        doc="Original filename"
    )
    
    file_size = Column(
        String(20),
        nullable=True,
        doc="File size in bytes"
    )
    
    file_hash = Column(
        String(64),
        nullable=False,
        doc="SHA-256 hash of the file for integrity"
    )
    
    mime_type = Column(
        String(100),
        nullable=True,
        doc="MIME type of the file"
    )
    
    # Encrypted document details
    document_number = Column(
        String(255),
        nullable=True,
        doc="Encrypted document number (passport, license, etc.)"
    )
    
    issuing_country = Column(
        String(2),
        nullable=True,
        doc="ISO 3166-1 alpha-2 country code of issuing country"
    )
    
    issue_date = Column(
        DateTime,
        nullable=True,
        doc="Document issue date"
    )
    
    expiry_date = Column(
        DateTime,
        nullable=True,
        doc="Document expiry date"
    )
    
    # Verification status
    is_verified = Column(
        String(20),
        default="pending",
        nullable=False,
        doc="Document verification status (pending, verified, rejected)"
    )
    
    verification_notes = Column(
        Text,
        nullable=True,
        doc="Notes from document verification"
    )
    
    # Relationships
    kyc_check = relationship(
        "KYCCheck",
        back_populates="documents",
        doc="KYC check associated with this document"
    )
    
    def __repr__(self) -> str:
        """String representation of the document."""
        return f"<Document(id={self.id}, type={self.document_type}, kyc_check_id={self.kyc_check_id})>"
    
    @property
    def is_expired(self) -> bool:
        """Check if document is expired."""
        if self.expiry_date:
            return datetime.utcnow() > self.expiry_date
        return False
    
    @property
    def days_until_expiry(self) -> Optional[int]:
        """Get days until document expires."""
        if self.expiry_date:
            delta = self.expiry_date - datetime.utcnow()
            return delta.days
        return None