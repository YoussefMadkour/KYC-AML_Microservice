"""
Mock KYC provider service for simulating external KYC verification workflows.
"""
import asyncio
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field

from app.models.kyc import DocumentType, KYCStatus
from app.utils.logging import get_logger


logger = get_logger(__name__)


class ProviderType(str, Enum):
    """Mock provider types."""
    JUMIO = "jumio"
    ONFIDO = "onfido"
    VERIFF = "veriff"
    SHUFTI_PRO = "shufti_pro"


class VerificationOutcome(str, Enum):
    """Possible verification outcomes."""
    APPROVED = "approved"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"
    PENDING = "pending"
    ERROR = "error"


class RiskLevel(str, Enum):
    """Risk assessment levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DocumentVerificationResult(BaseModel):
    """Document verification result."""
    
    document_type: DocumentType
    status: VerificationOutcome
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    extracted_data: Dict = Field(default_factory=dict)
    issues: List[str] = Field(default_factory=list)
    processing_time_ms: int = Field(..., gt=0)


class BiometricVerificationResult(BaseModel):
    """Biometric verification result."""
    
    face_match_score: float = Field(..., ge=0.0, le=1.0)
    liveness_score: float = Field(..., ge=0.0, le=1.0)
    quality_score: float = Field(..., ge=0.0, le=1.0)
    status: VerificationOutcome
    issues: List[str] = Field(default_factory=list)


class ProviderResponse(BaseModel):
    """Base provider response model."""
    
    provider_reference: str
    provider_type: ProviderType
    overall_status: VerificationOutcome
    risk_level: RiskLevel
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    processing_time_ms: int = Field(..., gt=0)
    created_at: datetime
    completed_at: Optional[datetime] = None
    webhook_url: Optional[str] = None
    
    # Detailed results
    document_results: List[DocumentVerificationResult] = Field(default_factory=list)
    biometric_result: Optional[BiometricVerificationResult] = None
    
    # Additional metadata
    metadata: Dict = Field(default_factory=dict)
    raw_response: Dict = Field(default_factory=dict)


class MockProviderInterface(ABC):
    """Abstract interface for mock KYC providers."""
    
    @abstractmethod
    async def submit_verification(
        self, 
        documents: List[Dict], 
        user_data: Dict,
        webhook_url: Optional[str] = None
    ) -> ProviderResponse:
        """
        Submit KYC verification request.
        
        Args:
            documents: List of document data
            user_data: User information
            webhook_url: Optional webhook URL for callbacks
            
        Returns:
            Provider response
        """
        pass
    
    @abstractmethod
    async def get_verification_result(self, provider_reference: str) -> Optional[ProviderResponse]:
        """
        Get verification result by provider reference.
        
        Args:
            provider_reference: Provider's reference ID
            
        Returns:
            Provider response if found
        """
        pass
    
    @abstractmethod
    def get_provider_type(self) -> ProviderType:
        """Get provider type."""
        pass


class BaseMockProvider(MockProviderInterface):
    """Base implementation for mock KYC providers."""
    
    def __init__(
        self, 
        provider_type: ProviderType,
        min_processing_delay: float = 1.0,
        max_processing_delay: float = 5.0,
        success_rate: float = 0.8,
        manual_review_rate: float = 0.15
    ):
        """
        Initialize mock provider.
        
        Args:
            provider_type: Type of provider
            min_processing_delay: Minimum processing delay in seconds
            max_processing_delay: Maximum processing delay in seconds
            success_rate: Rate of successful verifications (0.0-1.0)
            manual_review_rate: Rate of manual reviews (0.0-1.0)
        """
        self.provider_type = provider_type
        self.min_processing_delay = min_processing_delay
        self.max_processing_delay = max_processing_delay
        self.success_rate = success_rate
        self.manual_review_rate = manual_review_rate
        
        # In-memory storage for demo purposes
        self._verification_results: Dict[str, ProviderResponse] = {}
    
    async def submit_verification(
        self, 
        documents: List[Dict], 
        user_data: Dict,
        webhook_url: Optional[str] = None
    ) -> ProviderResponse:
        """Submit KYC verification request."""
        logger.info(f"Submitting verification to {self.provider_type} provider")
        
        provider_reference = self._generate_reference()
        start_time = time.time()
        
        # Simulate processing delay
        processing_delay = random.uniform(self.min_processing_delay, self.max_processing_delay)
        await asyncio.sleep(processing_delay)
        
        # Generate verification results
        document_results = []
        for doc in documents:
            doc_result = self._generate_document_result(doc)
            document_results.append(doc_result)
        
        # Generate biometric result if applicable
        biometric_result = None
        if any(doc.get("document_type") in [DocumentType.PASSPORT, DocumentType.DRIVER_LICENSE] for doc in documents):
            biometric_result = self._generate_biometric_result()
        
        # Determine overall outcome
        overall_status, risk_level, confidence_score = self._determine_overall_outcome(
            document_results, biometric_result
        )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Create response
        response = ProviderResponse(
            provider_reference=provider_reference,
            provider_type=self.provider_type,
            overall_status=overall_status,
            risk_level=risk_level,
            confidence_score=confidence_score,
            processing_time_ms=processing_time_ms,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            webhook_url=webhook_url,
            document_results=document_results,
            biometric_result=biometric_result,
            metadata=self._generate_metadata(user_data),
            raw_response=self._generate_raw_response(provider_reference, overall_status)
        )
        
        # Store result
        self._verification_results[provider_reference] = response
        
        logger.info(
            f"Verification completed for {provider_reference}: {overall_status} "
            f"(risk: {risk_level}, confidence: {confidence_score:.2f})"
        )
        
        return response
    
    async def get_verification_result(self, provider_reference: str) -> Optional[ProviderResponse]:
        """Get verification result by provider reference."""
        return self._verification_results.get(provider_reference)
    
    def get_provider_type(self) -> ProviderType:
        """Get provider type."""
        return self.provider_type
    
    def _generate_reference(self) -> str:
        """Generate provider reference ID."""
        prefix = self.provider_type.value.upper()[:3]
        return f"{prefix}_{uuid4().hex[:12].upper()}"
    
    def _generate_document_result(self, document: Dict) -> DocumentVerificationResult:
        """Generate document verification result."""
        doc_type = document.get("document_type", DocumentType.PASSPORT)
        
        # Simulate different outcomes based on document type and random factors
        outcome_weights = self._get_document_outcome_weights(doc_type)
        status = random.choices(
            list(outcome_weights.keys()),
            weights=list(outcome_weights.values())
        )[0]
        
        confidence_score = self._generate_confidence_score(status)
        issues = self._generate_document_issues(doc_type, status)
        extracted_data = self._generate_extracted_data(doc_type, document)
        
        return DocumentVerificationResult(
            document_type=doc_type,
            status=status,
            confidence_score=confidence_score,
            extracted_data=extracted_data,
            issues=issues,
            processing_time_ms=random.randint(500, 3000)
        )
    
    def _generate_biometric_result(self) -> BiometricVerificationResult:
        """Generate biometric verification result."""
        # Simulate biometric matching
        face_match_score = random.uniform(0.6, 0.99)
        liveness_score = random.uniform(0.7, 0.98)
        quality_score = random.uniform(0.65, 0.95)
        
        # Determine status based on scores
        if face_match_score > 0.85 and liveness_score > 0.8 and quality_score > 0.7:
            status = VerificationOutcome.APPROVED
            issues = []
        elif face_match_score < 0.7 or liveness_score < 0.75:
            status = VerificationOutcome.REJECTED
            issues = ["Low biometric match score", "Potential identity mismatch"]
        else:
            status = VerificationOutcome.MANUAL_REVIEW
            issues = ["Borderline biometric scores require manual review"]
        
        return BiometricVerificationResult(
            face_match_score=face_match_score,
            liveness_score=liveness_score,
            quality_score=quality_score,
            status=status,
            issues=issues
        )
    
    def _get_document_outcome_weights(self, doc_type: DocumentType) -> Dict[VerificationOutcome, float]:
        """Get outcome weights for different document types."""
        base_weights = {
            VerificationOutcome.APPROVED: self.success_rate,
            VerificationOutcome.MANUAL_REVIEW: self.manual_review_rate,
            VerificationOutcome.REJECTED: 1.0 - self.success_rate - self.manual_review_rate
        }
        
        # Adjust weights based on document type
        if doc_type == DocumentType.PASSPORT:
            # Passports are generally more reliable
            base_weights[VerificationOutcome.APPROVED] *= 1.1
            base_weights[VerificationOutcome.REJECTED] *= 0.8
        elif doc_type == DocumentType.UTILITY_BILL:
            # Utility bills are less reliable for identity verification
            base_weights[VerificationOutcome.APPROVED] *= 0.9
            base_weights[VerificationOutcome.MANUAL_REVIEW] *= 1.2
        
        return base_weights
    
    def _generate_confidence_score(self, status: VerificationOutcome) -> float:
        """Generate confidence score based on status."""
        if status == VerificationOutcome.APPROVED:
            return random.uniform(0.85, 0.99)
        elif status == VerificationOutcome.REJECTED:
            return random.uniform(0.1, 0.4)
        elif status == VerificationOutcome.MANUAL_REVIEW:
            return random.uniform(0.5, 0.8)
        else:
            return random.uniform(0.3, 0.7)
    
    def _generate_document_issues(self, doc_type: DocumentType, status: VerificationOutcome) -> List[str]:
        """Generate realistic document issues."""
        if status == VerificationOutcome.APPROVED:
            return []
        
        possible_issues = {
            DocumentType.PASSPORT: [
                "Document image quality is poor",
                "Some text is not clearly visible",
                "Document appears to be a photocopy",
                "Security features could not be verified",
                "Expiry date is approaching"
            ],
            DocumentType.DRIVER_LICENSE: [
                "License format not recognized",
                "Image quality insufficient for OCR",
                "Potential tampering detected",
                "Address information unclear",
                "License may be expired"
            ],
            DocumentType.UTILITY_BILL: [
                "Bill is older than 3 months",
                "Address does not match other documents",
                "Document appears to be edited",
                "Utility company not recognized",
                "Image quality is poor"
            ]
        }
        
        doc_issues = possible_issues.get(doc_type, ["Generic document issue"])
        
        if status == VerificationOutcome.REJECTED:
            return random.sample(doc_issues, min(3, len(doc_issues)))
        elif status == VerificationOutcome.MANUAL_REVIEW:
            return random.sample(doc_issues, min(2, len(doc_issues)))
        
        return []
    
    def _generate_extracted_data(self, doc_type: DocumentType, document: Dict) -> Dict:
        """Generate extracted data from document."""
        base_data = {
            "document_number": document.get("document_number", "EXTRACTED123456"),
            "issuing_country": document.get("issuing_country", "US"),
            "issue_date": document.get("issue_date"),
            "expiry_date": document.get("expiry_date")
        }
        
        if doc_type == DocumentType.PASSPORT:
            base_data.update({
                "nationality": random.choice(["US", "GB", "CA", "AU", "DE"]),
                "place_of_birth": "New York, NY",
                "passport_type": "P"
            })
        elif doc_type == DocumentType.DRIVER_LICENSE:
            base_data.update({
                "license_class": "C",
                "restrictions": "NONE",
                "endorsements": "NONE"
            })
        elif doc_type == DocumentType.UTILITY_BILL:
            base_data.update({
                "utility_type": "ELECTRICITY",
                "account_number": "ACC" + str(random.randint(100000, 999999)),
                "billing_period": "2024-01"
            })
        
        return base_data
    
    def _determine_overall_outcome(
        self, 
        document_results: List[DocumentVerificationResult],
        biometric_result: Optional[BiometricVerificationResult]
    ) -> tuple[VerificationOutcome, RiskLevel, float]:
        """Determine overall verification outcome."""
        # Count outcomes
        approved_docs = sum(1 for doc in document_results if doc.status == VerificationOutcome.APPROVED)
        rejected_docs = sum(1 for doc in document_results if doc.status == VerificationOutcome.REJECTED)
        review_docs = sum(1 for doc in document_results if doc.status == VerificationOutcome.MANUAL_REVIEW)
        
        total_docs = len(document_results)
        avg_confidence = sum(doc.confidence_score for doc in document_results) / total_docs if total_docs > 0 else 0.5
        
        # Factor in biometric result
        if biometric_result:
            if biometric_result.status == VerificationOutcome.REJECTED:
                return VerificationOutcome.REJECTED, RiskLevel.HIGH, min(avg_confidence, 0.3)
            elif biometric_result.status == VerificationOutcome.MANUAL_REVIEW:
                review_docs += 1
        
        # Determine overall status
        if rejected_docs > 0 or avg_confidence < 0.4:
            overall_status = VerificationOutcome.REJECTED
            risk_level = RiskLevel.HIGH
        elif review_docs > 0 or avg_confidence < 0.7:
            overall_status = VerificationOutcome.MANUAL_REVIEW
            risk_level = RiskLevel.MEDIUM
        elif approved_docs == total_docs and avg_confidence > 0.8:
            overall_status = VerificationOutcome.APPROVED
            risk_level = RiskLevel.LOW
        else:
            overall_status = VerificationOutcome.MANUAL_REVIEW
            risk_level = RiskLevel.MEDIUM
        
        return overall_status, risk_level, avg_confidence
    
    def _generate_metadata(self, user_data: Dict) -> Dict:
        """Generate provider-specific metadata."""
        return {
            "user_id": user_data.get("user_id"),
            "submission_method": "api",
            "ip_address": "192.168.1.100",
            "user_agent": "KYC-Service/1.0",
            "processing_node": f"node-{random.randint(1, 5)}",
            "api_version": "v2.1"
        }
    
    def _generate_raw_response(self, provider_reference: str, status: VerificationOutcome) -> Dict:
        """Generate provider-specific raw response format."""
        return {
            "id": provider_reference,
            "status": status.value,
            "created_at": datetime.utcnow().isoformat(),
            "provider": self.provider_type.value,
            "version": "2.1.0"
        }


class JumioMockProvider(BaseMockProvider):
    """Mock Jumio provider implementation."""
    
    def __init__(self, **kwargs):
        super().__init__(ProviderType.JUMIO, **kwargs)
    
    def _generate_raw_response(self, provider_reference: str, status: VerificationOutcome) -> Dict:
        """Generate Jumio-specific response format."""
        jumio_status_map = {
            VerificationOutcome.APPROVED: "PASSED",
            VerificationOutcome.REJECTED: "FAILED",
            VerificationOutcome.MANUAL_REVIEW: "REVIEW",
            VerificationOutcome.PENDING: "PENDING"
        }
        
        return {
            "scanReference": provider_reference,
            "status": jumio_status_map.get(status, "PENDING"),
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "WEB",
            "merchantScanReference": f"merchant_{uuid4().hex[:8]}"
        }


class OnfidoMockProvider(BaseMockProvider):
    """Mock Onfido provider implementation."""
    
    def __init__(self, **kwargs):
        super().__init__(ProviderType.ONFIDO, **kwargs)
    
    def _generate_raw_response(self, provider_reference: str, status: VerificationOutcome) -> Dict:
        """Generate Onfido-specific response format."""
        onfido_status_map = {
            VerificationOutcome.APPROVED: "complete",
            VerificationOutcome.REJECTED: "complete",
            VerificationOutcome.MANUAL_REVIEW: "awaiting_approval",
            VerificationOutcome.PENDING: "in_progress"
        }
        
        return {
            "id": provider_reference,
            "status": onfido_status_map.get(status, "in_progress"),
            "created_at": datetime.utcnow().isoformat(),
            "href": f"/v3.6/checks/{provider_reference}",
            "applicant_id": f"applicant_{uuid4().hex[:12]}"
        }


class VeriffMockProvider(BaseMockProvider):
    """Mock Veriff provider implementation."""
    
    def __init__(self, **kwargs):
        super().__init__(ProviderType.VERIFF, **kwargs)
    
    def _generate_raw_response(self, provider_reference: str, status: VerificationOutcome) -> Dict:
        """Generate Veriff-specific response format."""
        veriff_status_map = {
            VerificationOutcome.APPROVED: "approved",
            VerificationOutcome.REJECTED: "declined",
            VerificationOutcome.MANUAL_REVIEW: "review",
            VerificationOutcome.PENDING: "submitted"
        }
        
        return {
            "verification": {
                "id": provider_reference,
                "status": veriff_status_map.get(status, "submitted"),
                "sessionToken": f"session_{uuid4().hex[:16]}",
                "createdAt": datetime.utcnow().isoformat()
            }
        }


class MockProviderFactory:
    """Factory for creating mock providers."""
    
    _providers = {
        ProviderType.JUMIO: JumioMockProvider,
        ProviderType.ONFIDO: OnfidoMockProvider,
        ProviderType.VERIFF: VeriffMockProvider,
        ProviderType.SHUFTI_PRO: BaseMockProvider
    }
    
    @classmethod
    def create_provider(
        self, 
        provider_type: Union[ProviderType, str],
        **kwargs
    ) -> MockProviderInterface:
        """
        Create a mock provider instance.
        
        Args:
            provider_type: Type of provider to create
            **kwargs: Additional configuration options
            
        Returns:
            Mock provider instance
            
        Raises:
            ValueError: If provider type is not supported
        """
        if isinstance(provider_type, str):
            try:
                provider_type = ProviderType(provider_type)
            except ValueError:
                raise ValueError(f"Unsupported provider type: {provider_type}")
        
        provider_class = self._providers.get(provider_type)
        if not provider_class:
            raise ValueError(f"No implementation for provider type: {provider_type}")
        
        if provider_type == ProviderType.SHUFTI_PRO:
            return provider_class(provider_type, **kwargs)
        
        return provider_class(**kwargs)
    
    @classmethod
    def get_available_providers(cls) -> List[ProviderType]:
        """Get list of available provider types."""
        return list(cls._providers.keys())


class MockProviderService:
    """Service for managing mock KYC providers."""
    
    def __init__(self):
        """Initialize mock provider service."""
        self._providers: Dict[ProviderType, MockProviderInterface] = {}
        self._default_config = {
            "min_processing_delay": 1.0,
            "max_processing_delay": 5.0,
            "success_rate": 0.8,
            "manual_review_rate": 0.15
        }
    
    def get_provider(self, provider_type: Union[ProviderType, str]) -> MockProviderInterface:
        """
        Get or create a provider instance.
        
        Args:
            provider_type: Type of provider
            
        Returns:
            Provider instance
        """
        if isinstance(provider_type, str):
            provider_type = ProviderType(provider_type)
        
        if provider_type not in self._providers:
            self._providers[provider_type] = MockProviderFactory.create_provider(
                provider_type, **self._default_config
            )
        
        return self._providers[provider_type]
    
    async def submit_kyc_verification(
        self,
        provider_type: Union[ProviderType, str],
        documents: List[Dict],
        user_data: Dict,
        webhook_url: Optional[str] = None
    ) -> ProviderResponse:
        """
        Submit KYC verification to specified provider.
        
        Args:
            provider_type: Provider to use
            documents: Document data
            user_data: User information
            webhook_url: Optional webhook URL
            
        Returns:
            Provider response
        """
        provider = self.get_provider(provider_type)
        return await provider.submit_verification(documents, user_data, webhook_url)
    
    async def get_verification_result(
        self,
        provider_type: Union[ProviderType, str],
        provider_reference: str
    ) -> Optional[ProviderResponse]:
        """
        Get verification result from provider.
        
        Args:
            provider_type: Provider type
            provider_reference: Provider reference ID
            
        Returns:
            Provider response if found
        """
        provider = self.get_provider(provider_type)
        return await provider.get_verification_result(provider_reference)
    
    def configure_provider(
        self,
        provider_type: Union[ProviderType, str],
        **config
    ) -> None:
        """
        Configure provider settings.
        
        Args:
            provider_type: Provider type
            **config: Configuration options
        """
        if isinstance(provider_type, str):
            provider_type = ProviderType(provider_type)
        
        # Remove existing provider to force recreation with new config
        if provider_type in self._providers:
            del self._providers[provider_type]
        
        # Update default config
        updated_config = {**self._default_config, **config}
        self._providers[provider_type] = MockProviderFactory.create_provider(
            provider_type, **updated_config
        )
    
    def get_provider_statistics(self) -> Dict[str, Dict]:
        """Get statistics for all providers."""
        stats = {}
        for provider_type, provider in self._providers.items():
            if hasattr(provider, '_verification_results'):
                results = provider._verification_results
                total = len(results)
                if total > 0:
                    approved = sum(1 for r in results.values() if r.overall_status == VerificationOutcome.APPROVED)
                    rejected = sum(1 for r in results.values() if r.overall_status == VerificationOutcome.REJECTED)
                    review = sum(1 for r in results.values() if r.overall_status == VerificationOutcome.MANUAL_REVIEW)
                    
                    stats[provider_type.value] = {
                        "total_verifications": total,
                        "approved": approved,
                        "rejected": rejected,
                        "manual_review": review,
                        "approval_rate": approved / total if total > 0 else 0,
                        "avg_processing_time_ms": sum(r.processing_time_ms for r in results.values()) / total
                    }
        
        return stats