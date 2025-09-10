"""
KYC request and response schemas.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator

from app.models.kyc import DocumentType, KYCStatus


class DocumentBase(BaseModel):
    """Base document schema."""
    
    document_type: DocumentType = Field(..., description="Type of document")
    file_name: str = Field(..., min_length=1, max_length=255, description="Original filename")
    document_number: Optional[str] = Field(None, description="Document number (will be encrypted)")
    issuing_country: Optional[str] = Field(None, max_length=2, description="ISO 3166-1 alpha-2 country code")
    issue_date: Optional[datetime] = Field(None, description="Document issue date")
    expiry_date: Optional[datetime] = Field(None, description="Document expiry date")
    
    @validator("issuing_country")
    def validate_country_code(cls, v):
        """Validate country code format."""
        if v and len(v) != 2:
            raise ValueError("Country code must be 2 characters (ISO 3166-1 alpha-2)")
        return v.upper() if v else v


class DocumentCreate(DocumentBase):
    """Document creation schema."""
    
    file_path: str = Field(..., description="Path to the stored document file")
    file_size: Optional[str] = Field(None, description="File size in bytes")
    file_hash: str = Field(..., description="SHA-256 hash of the file")
    mime_type: Optional[str] = Field(None, description="MIME type of the file")


class DocumentResponse(DocumentBase):
    """Document response schema."""
    
    id: str = Field(..., description="Document ID")
    kyc_check_id: str = Field(..., description="Associated KYC check ID")
    file_size: Optional[str] = Field(None, description="File size in bytes")
    file_hash: str = Field(..., description="SHA-256 hash of the file")
    mime_type: Optional[str] = Field(None, description="MIME type of the file")
    is_verified: str = Field(..., description="Document verification status")
    verification_notes: Optional[str] = Field(None, description="Verification notes")
    is_expired: bool = Field(..., description="Whether document is expired")
    days_until_expiry: Optional[int] = Field(None, description="Days until expiry")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class KYCCheckBase(BaseModel):
    """Base KYC check schema."""
    
    provider: str = Field(..., min_length=1, max_length=100, description="KYC provider name")


class KYCCheckCreate(KYCCheckBase):
    """KYC check creation schema."""
    
    documents: List[DocumentCreate] = Field(..., min_items=1, description="Documents for verification")
    notes: Optional[str] = Field(None, description="Additional notes")


class KYCCheckUpdate(BaseModel):
    """KYC check update schema."""
    
    status: Optional[KYCStatus] = Field(None, description="New status")
    provider_reference: Optional[str] = Field(None, description="Provider reference ID")
    verification_result: Optional[dict] = Field(None, description="Verification results")
    risk_score: Optional[str] = Field(None, description="Risk score")
    notes: Optional[str] = Field(None, description="Additional notes")
    rejection_reason: Optional[str] = Field(None, description="Rejection reason")


class KYCCheckResponse(KYCCheckBase):
    """KYC check response schema."""
    
    id: str = Field(..., description="KYC check ID")
    user_id: str = Field(..., description="User ID")
    status: KYCStatus = Field(..., description="Current status")
    provider_reference: Optional[str] = Field(None, description="Provider reference ID")
    verification_result: Optional[dict] = Field(None, description="Verification results")
    risk_score: Optional[str] = Field(None, description="Risk score")
    submitted_at: str = Field(..., description="Submission timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")
    expires_at: Optional[str] = Field(None, description="Expiration timestamp")
    notes: Optional[str] = Field(None, description="Additional notes")
    rejection_reason: Optional[str] = Field(None, description="Rejection reason")
    is_completed: bool = Field(..., description="Whether verification is completed")
    is_pending_review: bool = Field(..., description="Whether needs manual review")
    processing_time_seconds: Optional[int] = Field(None, description="Processing time in seconds")
    documents: List[DocumentResponse] = Field(default=[], description="Associated documents")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class KYCCheckListResponse(BaseModel):
    """KYC check list response schema."""
    
    items: List[KYCCheckResponse] = Field(..., description="List of KYC checks")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total number of pages")


class KYCStatusUpdate(BaseModel):
    """KYC status update schema."""
    
    status: KYCStatus = Field(..., description="New status")
    notes: Optional[str] = Field(None, description="Update notes")
    rejection_reason: Optional[str] = Field(None, description="Rejection reason if applicable")
    
    @validator("rejection_reason")
    def validate_rejection_reason(cls, v, values):
        """Validate rejection reason is provided when status is rejected."""
        if values.get("status") == KYCStatus.REJECTED and not v:
            raise ValueError("Rejection reason is required when status is rejected")
        return v


class KYCHistoryEntry(BaseModel):
    """KYC history entry schema."""
    
    id: str = Field(..., description="History entry ID")
    kyc_check_id: str = Field(..., description="KYC check ID")
    previous_status: Optional[KYCStatus] = Field(None, description="Previous status")
    new_status: KYCStatus = Field(..., description="New status")
    changed_by: Optional[str] = Field(None, description="User who made the change")
    notes: Optional[str] = Field(None, description="Change notes")
    timestamp: str = Field(..., description="Change timestamp")
    
    class Config:
        from_attributes = True


class KYCHistoryResponse(BaseModel):
    """KYC history response schema."""
    
    kyc_check_id: str = Field(..., description="KYC check ID")
    history: List[KYCHistoryEntry] = Field(..., description="History entries")
    total_entries: int = Field(..., description="Total number of history entries")