"""
Unit tests for mock KYC provider service.
"""
import asyncio
import pytest
from unittest.mock import patch
from datetime import datetime

from app.services.mock_provider import (
    MockProviderService,
    MockProviderFactory,
    BaseMockProvider,
    JumioMockProvider,
    OnfidoMockProvider,
    VeriffMockProvider,
    ProviderType,
    VerificationOutcome,
    RiskLevel,
    DocumentVerificationResult,
    BiometricVerificationResult,
    ProviderResponse
)
from app.models.kyc import DocumentType


class TestBaseMockProvider:
    """Test cases for BaseMockProvider."""
    
    @pytest.fixture
    def provider(self):
        """Create a base mock provider for testing."""
        return BaseMockProvider(
            provider_type=ProviderType.JUMIO,
            min_processing_delay=0.1,
            max_processing_delay=0.2,
            success_rate=0.8,
            manual_review_rate=0.15
        )
    
    @pytest.fixture
    def sample_documents(self):
        """Sample documents for testing."""
        return [
            {
                "document_type": DocumentType.PASSPORT,
                "document_number": "P123456789",
                "issuing_country": "US",
                "file_path": "/tmp/passport.jpg"
            },
            {
                "document_type": DocumentType.UTILITY_BILL,
                "file_path": "/tmp/utility.pdf"
            }
        ]
    
    @pytest.fixture
    def sample_user_data(self):
        """Sample user data for testing."""
        return {
            "user_id": "user_123",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com"
        }
    
    def test_provider_initialization(self, provider):
        """Test provider initialization."""
        assert provider.provider_type == ProviderType.JUMIO
        assert provider.min_processing_delay == 0.1
        assert provider.max_processing_delay == 0.2
        assert provider.success_rate == 0.8
        assert provider.manual_review_rate == 0.15
        assert isinstance(provider._verification_results, dict)
    
    def test_get_provider_type(self, provider):
        """Test get_provider_type method."""
        assert provider.get_provider_type() == ProviderType.JUMIO
    
    def test_generate_reference(self, provider):
        """Test reference ID generation."""
        ref1 = provider._generate_reference()
        ref2 = provider._generate_reference()
        
        assert ref1 != ref2
        assert ref1.startswith("JUM_")
        assert len(ref1) == 16  # JUM_ + 12 hex chars
    
    def test_generate_confidence_score(self, provider):
        """Test confidence score generation."""
        approved_score = provider._generate_confidence_score(VerificationOutcome.APPROVED)
        rejected_score = provider._generate_confidence_score(VerificationOutcome.REJECTED)
        review_score = provider._generate_confidence_score(VerificationOutcome.MANUAL_REVIEW)
        
        assert 0.85 <= approved_score <= 0.99
        assert 0.1 <= rejected_score <= 0.4
        assert 0.5 <= review_score <= 0.8
    
    def test_generate_document_issues(self, provider):
        """Test document issues generation."""
        approved_issues = provider._generate_document_issues(DocumentType.PASSPORT, VerificationOutcome.APPROVED)
        rejected_issues = provider._generate_document_issues(DocumentType.PASSPORT, VerificationOutcome.REJECTED)
        review_issues = provider._generate_document_issues(DocumentType.PASSPORT, VerificationOutcome.MANUAL_REVIEW)
        
        assert approved_issues == []
        assert len(rejected_issues) > 0
        assert len(review_issues) > 0
        assert len(rejected_issues) >= len(review_issues)
    
    def test_generate_extracted_data(self, provider):
        """Test extracted data generation."""
        passport_doc = {
            "document_type": DocumentType.PASSPORT,
            "document_number": "P123456789",
            "issuing_country": "US"
        }
        
        extracted = provider._generate_extracted_data(DocumentType.PASSPORT, passport_doc)
        
        assert "document_number" in extracted
        assert "issuing_country" in extracted
        assert "nationality" in extracted
        assert "place_of_birth" in extracted
        assert "passport_type" in extracted
    
    def test_generate_document_result(self, provider):
        """Test document result generation."""
        document = {
            "document_type": DocumentType.PASSPORT,
            "document_number": "P123456789"
        }
        
        result = provider._generate_document_result(document)
        
        assert isinstance(result, DocumentVerificationResult)
        assert result.document_type == DocumentType.PASSPORT
        assert result.status in [VerificationOutcome.APPROVED, VerificationOutcome.REJECTED, VerificationOutcome.MANUAL_REVIEW]
        assert 0.0 <= result.confidence_score <= 1.0
        assert result.processing_time_ms > 0
        assert isinstance(result.extracted_data, dict)
        assert isinstance(result.issues, list)
    
    def test_generate_biometric_result(self, provider):
        """Test biometric result generation."""
        result = provider._generate_biometric_result()
        
        assert isinstance(result, BiometricVerificationResult)
        assert 0.0 <= result.face_match_score <= 1.0
        assert 0.0 <= result.liveness_score <= 1.0
        assert 0.0 <= result.quality_score <= 1.0
        assert result.status in [VerificationOutcome.APPROVED, VerificationOutcome.REJECTED, VerificationOutcome.MANUAL_REVIEW]
        assert isinstance(result.issues, list)
    
    def test_determine_overall_outcome_approved(self, provider):
        """Test overall outcome determination for approved case."""
        doc_results = [
            DocumentVerificationResult(
                document_type=DocumentType.PASSPORT,
                status=VerificationOutcome.APPROVED,
                confidence_score=0.9,
                processing_time_ms=1000
            )
        ]
        
        biometric_result = BiometricVerificationResult(
            face_match_score=0.9,
            liveness_score=0.9,
            quality_score=0.9,
            status=VerificationOutcome.APPROVED
        )
        
        status, risk, confidence = provider._determine_overall_outcome(doc_results, biometric_result)
        
        assert status == VerificationOutcome.APPROVED
        assert risk == RiskLevel.LOW
        assert confidence > 0.8
    
    def test_determine_overall_outcome_rejected(self, provider):
        """Test overall outcome determination for rejected case."""
        doc_results = [
            DocumentVerificationResult(
                document_type=DocumentType.PASSPORT,
                status=VerificationOutcome.REJECTED,
                confidence_score=0.2,
                processing_time_ms=1000
            )
        ]
        
        status, risk, confidence = provider._determine_overall_outcome(doc_results, None)
        
        assert status == VerificationOutcome.REJECTED
        assert risk == RiskLevel.HIGH
    
    @pytest.mark.asyncio
    async def test_submit_verification(self, provider, sample_documents, sample_user_data):
        """Test verification submission."""
        response = await provider.submit_verification(
            documents=sample_documents,
            user_data=sample_user_data,
            webhook_url="https://example.com/webhook"
        )
        
        assert isinstance(response, ProviderResponse)
        assert response.provider_type == ProviderType.JUMIO
        assert response.provider_reference.startswith("JUM_")
        assert response.overall_status in [VerificationOutcome.APPROVED, VerificationOutcome.REJECTED, VerificationOutcome.MANUAL_REVIEW]
        assert response.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]
        assert 0.0 <= response.confidence_score <= 1.0
        assert response.processing_time_ms > 0
        assert isinstance(response.created_at, datetime)
        assert response.webhook_url == "https://example.com/webhook"
        assert len(response.document_results) == len(sample_documents)
        assert response.biometric_result is not None  # Should have biometric for passport
        assert isinstance(response.metadata, dict)
        assert isinstance(response.raw_response, dict)
    
    @pytest.mark.asyncio
    async def test_get_verification_result(self, provider, sample_documents, sample_user_data):
        """Test getting verification result."""
        # First submit a verification
        response = await provider.submit_verification(sample_documents, sample_user_data)
        provider_reference = response.provider_reference
        
        # Then retrieve it
        retrieved = await provider.get_verification_result(provider_reference)
        
        assert retrieved is not None
        assert retrieved.provider_reference == provider_reference
        assert retrieved.provider_type == response.provider_type
    
    @pytest.mark.asyncio
    async def test_get_verification_result_not_found(self, provider):
        """Test getting non-existent verification result."""
        result = await provider.get_verification_result("NONEXISTENT_REF")
        assert result is None


class TestSpecificProviders:
    """Test cases for specific provider implementations."""
    
    def test_jumio_provider(self):
        """Test Jumio provider implementation."""
        provider = JumioMockProvider()
        assert provider.get_provider_type() == ProviderType.JUMIO
        
        raw_response = provider._generate_raw_response("JUM_123", VerificationOutcome.APPROVED)
        assert "scanReference" in raw_response
        assert raw_response["status"] == "PASSED"
        assert "timestamp" in raw_response
    
    def test_onfido_provider(self):
        """Test Onfido provider implementation."""
        provider = OnfidoMockProvider()
        assert provider.get_provider_type() == ProviderType.ONFIDO
        
        raw_response = provider._generate_raw_response("ONF_123", VerificationOutcome.APPROVED)
        assert raw_response["id"] == "ONF_123"
        assert raw_response["status"] == "complete"
        assert "href" in raw_response
    
    def test_veriff_provider(self):
        """Test Veriff provider implementation."""
        provider = VeriffMockProvider()
        assert provider.get_provider_type() == ProviderType.VERIFF
        
        raw_response = provider._generate_raw_response("VER_123", VerificationOutcome.MANUAL_REVIEW)
        assert raw_response["verification"]["id"] == "VER_123"
        assert raw_response["verification"]["status"] == "review"
        assert "sessionToken" in raw_response["verification"]


class TestMockProviderFactory:
    """Test cases for MockProviderFactory."""
    
    def test_create_jumio_provider(self):
        """Test creating Jumio provider."""
        provider = MockProviderFactory.create_provider(ProviderType.JUMIO)
        assert isinstance(provider, JumioMockProvider)
        assert provider.get_provider_type() == ProviderType.JUMIO
    
    def test_create_onfido_provider(self):
        """Test creating Onfido provider."""
        provider = MockProviderFactory.create_provider(ProviderType.ONFIDO)
        assert isinstance(provider, OnfidoMockProvider)
        assert provider.get_provider_type() == ProviderType.ONFIDO
    
    def test_create_veriff_provider(self):
        """Test creating Veriff provider."""
        provider = MockProviderFactory.create_provider(ProviderType.VERIFF)
        assert isinstance(provider, VeriffMockProvider)
        assert provider.get_provider_type() == ProviderType.VERIFF
    
    def test_create_provider_with_string(self):
        """Test creating provider with string type."""
        provider = MockProviderFactory.create_provider("jumio")
        assert isinstance(provider, JumioMockProvider)
    
    def test_create_provider_with_config(self):
        """Test creating provider with custom configuration."""
        provider = MockProviderFactory.create_provider(
            ProviderType.JUMIO,
            success_rate=0.9,
            manual_review_rate=0.05
        )
        assert provider.success_rate == 0.9
        assert provider.manual_review_rate == 0.05
    
    def test_create_provider_invalid_type(self):
        """Test creating provider with invalid type."""
        with pytest.raises(ValueError, match="Unsupported provider type"):
            MockProviderFactory.create_provider("invalid_provider")
    
    def test_get_available_providers(self):
        """Test getting available providers."""
        providers = MockProviderFactory.get_available_providers()
        assert ProviderType.JUMIO in providers
        assert ProviderType.ONFIDO in providers
        assert ProviderType.VERIFF in providers
        assert ProviderType.SHUFTI_PRO in providers


class TestMockProviderService:
    """Test cases for MockProviderService."""
    
    @pytest.fixture
    def service(self):
        """Create mock provider service for testing."""
        return MockProviderService()
    
    @pytest.fixture
    def sample_documents(self):
        """Sample documents for testing."""
        return [
            {
                "document_type": DocumentType.PASSPORT,
                "document_number": "P123456789",
                "issuing_country": "US"
            }
        ]
    
    @pytest.fixture
    def sample_user_data(self):
        """Sample user data for testing."""
        return {
            "user_id": "user_123",
            "first_name": "John",
            "last_name": "Doe"
        }
    
    def test_service_initialization(self, service):
        """Test service initialization."""
        assert isinstance(service._providers, dict)
        assert len(service._providers) == 0
        assert isinstance(service._default_config, dict)
    
    def test_get_provider(self, service):
        """Test getting provider instance."""
        provider = service.get_provider(ProviderType.JUMIO)
        assert isinstance(provider, JumioMockProvider)
        
        # Should return same instance on second call
        provider2 = service.get_provider(ProviderType.JUMIO)
        assert provider is provider2
    
    def test_get_provider_with_string(self, service):
        """Test getting provider with string type."""
        provider = service.get_provider("onfido")
        assert isinstance(provider, OnfidoMockProvider)
    
    @pytest.mark.asyncio
    async def test_submit_kyc_verification(self, service, sample_documents, sample_user_data):
        """Test submitting KYC verification."""
        response = await service.submit_kyc_verification(
            provider_type=ProviderType.JUMIO,
            documents=sample_documents,
            user_data=sample_user_data,
            webhook_url="https://example.com/webhook"
        )
        
        assert isinstance(response, ProviderResponse)
        assert response.provider_type == ProviderType.JUMIO
        assert response.webhook_url == "https://example.com/webhook"
    
    @pytest.mark.asyncio
    async def test_get_verification_result(self, service, sample_documents, sample_user_data):
        """Test getting verification result."""
        # Submit verification first
        response = await service.submit_kyc_verification(
            provider_type=ProviderType.JUMIO,
            documents=sample_documents,
            user_data=sample_user_data
        )
        
        # Get result
        result = await service.get_verification_result(
            provider_type=ProviderType.JUMIO,
            provider_reference=response.provider_reference
        )
        
        assert result is not None
        assert result.provider_reference == response.provider_reference
    
    def test_configure_provider(self, service):
        """Test configuring provider."""
        # First get a provider to create it
        provider1 = service.get_provider(ProviderType.JUMIO)
        original_success_rate = provider1.success_rate
        
        # Configure with new settings
        service.configure_provider(
            provider_type=ProviderType.JUMIO,
            success_rate=0.95,
            manual_review_rate=0.03
        )
        
        # Get provider again - should be new instance with new config
        provider2 = service.get_provider(ProviderType.JUMIO)
        assert provider2 is not provider1
        assert provider2.success_rate == 0.95
        assert provider2.manual_review_rate == 0.03
    
    @pytest.mark.asyncio
    async def test_get_provider_statistics(self, service, sample_documents, sample_user_data):
        """Test getting provider statistics."""
        # Submit a few verifications
        for _ in range(3):
            await service.submit_kyc_verification(
                provider_type=ProviderType.JUMIO,
                documents=sample_documents,
                user_data=sample_user_data
            )
        
        stats = service.get_provider_statistics()
        
        assert "jumio" in stats
        jumio_stats = stats["jumio"]
        assert jumio_stats["total_verifications"] == 3
        assert "approved" in jumio_stats
        assert "rejected" in jumio_stats
        assert "manual_review" in jumio_stats
        assert "approval_rate" in jumio_stats
        assert "avg_processing_time_ms" in jumio_stats
    
    def test_get_provider_statistics_empty(self, service):
        """Test getting statistics with no verifications."""
        stats = service.get_provider_statistics()
        assert isinstance(stats, dict)
        assert len(stats) == 0


class TestProviderResponseModel:
    """Test cases for ProviderResponse model."""
    
    def test_provider_response_creation(self):
        """Test creating ProviderResponse."""
        response = ProviderResponse(
            provider_reference="TEST_123",
            provider_type=ProviderType.JUMIO,
            overall_status=VerificationOutcome.APPROVED,
            risk_level=RiskLevel.LOW,
            confidence_score=0.95,
            processing_time_ms=2000,
            created_at=datetime.utcnow()
        )
        
        assert response.provider_reference == "TEST_123"
        assert response.provider_type == ProviderType.JUMIO
        assert response.overall_status == VerificationOutcome.APPROVED
        assert response.risk_level == RiskLevel.LOW
        assert response.confidence_score == 0.95
        assert response.processing_time_ms == 2000
    
    def test_provider_response_validation(self):
        """Test ProviderResponse validation."""
        with pytest.raises(ValueError):
            ProviderResponse(
                provider_reference="TEST_123",
                provider_type=ProviderType.JUMIO,
                overall_status=VerificationOutcome.APPROVED,
                risk_level=RiskLevel.LOW,
                confidence_score=1.5,  # Invalid: > 1.0
                processing_time_ms=2000,
                created_at=datetime.utcnow()
            )


class TestDocumentVerificationResult:
    """Test cases for DocumentVerificationResult model."""
    
    def test_document_result_creation(self):
        """Test creating DocumentVerificationResult."""
        result = DocumentVerificationResult(
            document_type=DocumentType.PASSPORT,
            status=VerificationOutcome.APPROVED,
            confidence_score=0.9,
            processing_time_ms=1500
        )
        
        assert result.document_type == DocumentType.PASSPORT
        assert result.status == VerificationOutcome.APPROVED
        assert result.confidence_score == 0.9
        assert result.processing_time_ms == 1500
        assert result.extracted_data == {}
        assert result.issues == []


class TestBiometricVerificationResult:
    """Test cases for BiometricVerificationResult model."""
    
    def test_biometric_result_creation(self):
        """Test creating BiometricVerificationResult."""
        result = BiometricVerificationResult(
            face_match_score=0.95,
            liveness_score=0.88,
            quality_score=0.92,
            status=VerificationOutcome.APPROVED
        )
        
        assert result.face_match_score == 0.95
        assert result.liveness_score == 0.88
        assert result.quality_score == 0.92
        assert result.status == VerificationOutcome.APPROVED
        assert result.issues == []