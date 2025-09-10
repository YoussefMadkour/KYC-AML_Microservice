"""
Example integration of KYC service with mock providers.
This demonstrates how the mock provider service would be used in practice.
"""

from typing import Dict, List, Optional
from uuid import UUID

from app.models.kyc import KYCStatus
from app.schemas.kyc import KYCCheckResponse
from app.services.kyc_service import KYCService
from app.services.mock_provider import MockProviderService, ProviderType
from app.utils.logging import get_logger

logger = get_logger(__name__)


class KYCIntegrationService:
    """Service demonstrating integration between KYC service and mock providers."""

    def __init__(self, kyc_service: KYCService):
        """
        Initialize integration service.

        Args:
            kyc_service: KYC service instance
        """
        self.kyc_service = kyc_service
        self.mock_provider_service = MockProviderService()

    async def process_kyc_with_mock_provider(
        self, kyc_check_id: UUID, provider_type: str = "jumio"
    ) -> Optional[KYCCheckResponse]:
        """
        Process KYC check using mock provider.

        Args:
            kyc_check_id: KYC check ID
            provider_type: Provider type to use

        Returns:
            Updated KYC check response
        """
        logger.info(
            f"Processing KYC check {kyc_check_id} with mock provider {provider_type}"
        )

        # Get the KYC check
        kyc_check = self.kyc_service.get_kyc_check(kyc_check_id)
        if not kyc_check:
            logger.error(f"KYC check {kyc_check_id} not found")
            return None

        if kyc_check.status != KYCStatus.PENDING:
            logger.warning(
                f"KYC check {kyc_check_id} is not in pending status: {kyc_check.status}"
            )
            return kyc_check

        try:
            # Update status to in_progress
            from app.schemas.kyc import KYCStatusUpdate

            status_update = KYCStatusUpdate(
                status=KYCStatus.IN_PROGRESS, notes="Processing with mock provider"
            )

            updated_check = self.kyc_service.update_kyc_status(
                kyc_check_id, status_update, "mock_provider_integration"
            )

            if not updated_check:
                logger.error(
                    f"Failed to update KYC check {kyc_check_id} to in_progress"
                )
                return None

            # Prepare documents for mock provider
            documents = []
            for doc in kyc_check.documents:
                doc_data = {
                    "document_type": doc.document_type,
                    "document_number": doc.document_number,
                    "issuing_country": doc.issuing_country,
                    "file_path": f"/mock/path/{doc.file_name}",
                }
                documents.append(doc_data)

            # Prepare user data
            user_data = {
                "user_id": str(kyc_check.user_id),
                "kyc_check_id": str(kyc_check_id),
            }

            # Submit to mock provider
            provider_response = (
                await self.mock_provider_service.submit_kyc_verification(
                    provider_type=provider_type,
                    documents=documents,
                    user_data=user_data,
                    webhook_url="https://api.example.com/webhooks/kyc",
                )
            )

            # Map provider response to KYC status
            final_status = self._map_provider_status_to_kyc_status(
                provider_response.overall_status
            )

            # Update KYC check with results
            from app.schemas.kyc import KYCCheckUpdate

            update_data = KYCCheckUpdate(
                status=final_status,
                provider_reference=provider_response.provider_reference,
                verification_result={
                    "provider_type": provider_response.provider_type.value,
                    "confidence_score": provider_response.confidence_score,
                    "risk_level": provider_response.risk_level.value,
                    "processing_time_ms": provider_response.processing_time_ms,
                    "document_results": [
                        {
                            "document_type": doc_result.document_type.value,
                            "status": doc_result.status.value,
                            "confidence_score": doc_result.confidence_score,
                            "issues": doc_result.issues,
                            "extracted_data": doc_result.extracted_data,
                        }
                        for doc_result in provider_response.document_results
                    ],
                    "biometric_result": (
                        {
                            "face_match_score": provider_response.biometric_result.face_match_score,
                            "liveness_score": provider_response.biometric_result.liveness_score,
                            "quality_score": provider_response.biometric_result.quality_score,
                            "status": provider_response.biometric_result.status.value,
                        }
                        if provider_response.biometric_result
                        else None
                    ),
                    "raw_response": provider_response.raw_response,
                },
                risk_score=provider_response.risk_level.value,
                notes=f"Processed by {provider_type} mock provider",
            )

            final_check = self.kyc_service.update_kyc_check(
                kyc_check_id, update_data, "mock_provider_integration"
            )

            logger.info(
                f"Completed KYC check {kyc_check_id} with status {final_status} "
                f"(confidence: {provider_response.confidence_score:.2f})"
            )

            return final_check

        except Exception as e:
            logger.error(
                f"Error processing KYC check {kyc_check_id} with mock provider: {str(e)}"
            )

            # Update to error status
            error_update = KYCStatusUpdate(
                status=KYCStatus.REJECTED,
                notes=f"Processing failed: {str(e)}",
                rejection_reason="Technical error during verification",
            )

            return self.kyc_service.update_kyc_status(
                kyc_check_id, error_update, "mock_provider_integration"
            )

    def _map_provider_status_to_kyc_status(self, provider_status: str) -> KYCStatus:
        """
        Map provider verification outcome to KYC status.

        Args:
            provider_status: Provider verification outcome

        Returns:
            Corresponding KYC status
        """
        status_mapping = {
            "approved": KYCStatus.APPROVED,
            "rejected": KYCStatus.REJECTED,
            "manual_review": KYCStatus.MANUAL_REVIEW,
            "pending": KYCStatus.IN_PROGRESS,
            "error": KYCStatus.REJECTED,
        }

        return status_mapping.get(provider_status, KYCStatus.MANUAL_REVIEW)

    def get_provider_statistics(self) -> Dict:
        """
        Get statistics from all mock providers.

        Returns:
            Provider statistics
        """
        return self.mock_provider_service.get_provider_statistics()

    def configure_mock_provider(
        self,
        provider_type: str,
        success_rate: float = 0.8,
        manual_review_rate: float = 0.15,
        min_delay: float = 1.0,
        max_delay: float = 5.0,
    ) -> None:
        """
        Configure mock provider settings.

        Args:
            provider_type: Provider type to configure
            success_rate: Success rate (0.0-1.0)
            manual_review_rate: Manual review rate (0.0-1.0)
            min_delay: Minimum processing delay in seconds
            max_delay: Maximum processing delay in seconds
        """
        self.mock_provider_service.configure_provider(
            provider_type=provider_type,
            success_rate=success_rate,
            manual_review_rate=manual_review_rate,
            min_processing_delay=min_delay,
            max_processing_delay=max_delay,
        )

        logger.info(
            f"Configured {provider_type} provider: "
            f"success_rate={success_rate}, manual_review_rate={manual_review_rate}, "
            f"delay={min_delay}-{max_delay}s"
        )


# Example usage function
async def example_kyc_processing():
    """
    Example of how to use the KYC integration with mock providers.
    This would typically be called from a Celery task or API endpoint.
    """
    from sqlalchemy.orm import Session

    from app.database import get_db

    # This is just an example - in practice you'd get the session from dependency injection
    db: Session = next(get_db())

    try:
        # Initialize services
        kyc_service = KYCService(db)
        integration_service = KYCIntegrationService(kyc_service)

        # Configure providers for different scenarios
        integration_service.configure_mock_provider(
            provider_type="jumio",
            success_rate=0.85,
            manual_review_rate=0.10,
            min_delay=2.0,
            max_delay=8.0,
        )

        integration_service.configure_mock_provider(
            provider_type="onfido",
            success_rate=0.80,
            manual_review_rate=0.15,
            min_delay=1.5,
            max_delay=6.0,
        )

        # Example: Process a KYC check
        # kyc_check_id = UUID("some-uuid-here")
        # result = await integration_service.process_kyc_with_mock_provider(
        #     kyc_check_id=kyc_check_id,
        #     provider_type="jumio"
        # )

        # Get provider statistics
        stats = integration_service.get_provider_statistics()
        logger.info(f"Provider statistics: {stats}")

    finally:
        db.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_kyc_processing())
