"""
Webhook authentication middleware for FastAPI.
"""
import json
import logging
from typing import Callable, Dict, Optional

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.webhook_security import (
    WebhookProvider,
    WebhookSecurityError,
    webhook_signature_verifier
)

logger = logging.getLogger(__name__)


class WebhookAuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to authenticate webhook requests based on signatures.
    
    This middleware automatically validates webhook signatures for requests
    to webhook endpoints based on the provider specified in the URL path.
    """
    
    def __init__(
        self,
        app,
        webhook_paths: Optional[Dict[str, str]] = None,
        require_timestamp_validation: bool = True,
        log_verification_details: bool = True
    ):
        """
        Initialize webhook authentication middleware.
        
        Args:
            app: FastAPI application instance
            webhook_paths: Dictionary mapping URL patterns to webhook validation
            require_timestamp_validation: Whether to require timestamp validation
            log_verification_details: Whether to log verification details
        """
        super().__init__(app)
        
        # Default webhook paths that require authentication
        self.webhook_paths = webhook_paths or {
            "/webhooks/kyc/": "webhook",
            "/webhooks/aml/": "webhook",
            "/api/v1/webhooks/": "webhook"
        }
        
        self.require_timestamp_validation = require_timestamp_validation
        self.log_verification_details = log_verification_details
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process webhook authentication for matching requests.
        
        Args:
            request: The incoming HTTP request
            call_next: The next middleware/handler in the chain
            
        Returns:
            HTTP response
        """
        # Check if this is a webhook request that needs authentication
        if not self._is_webhook_request(request):
            return await call_next(request)
        
        # Extract provider from URL path
        provider = self._extract_provider_from_path(request.url.path)
        if not provider:
            logger.warning(f"Could not extract provider from webhook path: {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook endpoint - provider not specified"
            )
        
        # Read request body
        try:
            body = await request.body()
            payload = body.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to read webhook request body: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request body"
            )
        
        # Convert headers to dictionary
        headers = dict(request.headers)
        
        # Verify webhook signature
        try:
            is_valid, verification_details = webhook_signature_verifier.verify_webhook_request(
                payload=payload,
                headers=headers,
                provider=provider,
                validate_timestamp=self.require_timestamp_validation
            )
            
            if self.log_verification_details:
                logger.info(
                    f"Webhook verification for {provider}: "
                    f"valid={is_valid}, details={verification_details}"
                )
            
            if not is_valid:
                error_message = verification_details.get("error_message", "Signature verification failed")
                logger.warning(
                    f"Webhook signature verification failed for {provider}: {error_message}"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Webhook authentication failed: {error_message}"
                )
            
            # Add verification details to request state for use in handlers
            request.state.webhook_verified = True
            request.state.webhook_provider = provider
            request.state.webhook_verification_details = verification_details
            
            logger.info(f"Webhook signature verified successfully for provider: {provider}")
            
        except WebhookSecurityError as e:
            logger.error(f"Webhook security error for {provider}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Webhook security error: {str(e)}"
            )
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error during webhook verification: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during webhook verification"
            )
        
        # Continue to the actual webhook handler
        return await call_next(request)
    
    def _is_webhook_request(self, request: Request) -> bool:
        """
        Check if the request is a webhook request that needs authentication.
        
        Args:
            request: The HTTP request
            
        Returns:
            True if this is a webhook request, False otherwise
        """
        path = request.url.path
        method = request.method
        
        # Only authenticate POST requests to webhook endpoints
        if method != "POST":
            return False
        
        # Check if path matches any webhook patterns
        for webhook_path in self.webhook_paths:
            if webhook_path in path:
                return True
        
        return False
    
    def _extract_provider_from_path(self, path: str) -> Optional[WebhookProvider]:
        """
        Extract webhook provider from URL path.
        
        Args:
            path: The URL path
            
        Returns:
            WebhookProvider enum value or None if not found
        """
        # Expected path formats:
        # /webhooks/kyc/{provider}
        # /webhooks/aml/{provider}
        # /api/v1/webhooks/{type}/{provider}
        
        path_parts = path.strip('/').split('/')
        
        # Look for provider in different path positions
        provider_candidates = []
        
        if len(path_parts) >= 3:
            # /webhooks/kyc/{provider} or /webhooks/aml/{provider}
            if path_parts[0] == "webhooks" and path_parts[1] in ["kyc", "aml"]:
                provider_candidates.append(path_parts[2])
        
        if len(path_parts) >= 5:
            # /api/v1/webhooks/{type}/{provider}
            if (path_parts[0] == "api" and path_parts[1] == "v1" and 
                path_parts[2] == "webhooks"):
                provider_candidates.append(path_parts[4])
        
        # Try to match provider candidates with known providers
        for candidate in provider_candidates:
            try:
                return WebhookProvider(candidate)
            except ValueError:
                continue
        
        return None


class WebhookAuthDependency:
    """
    FastAPI dependency for webhook authentication.
    
    This can be used as an alternative to middleware for more granular control.
    """
    
    def __init__(
        self,
        require_timestamp_validation: bool = True,
        log_verification_details: bool = True
    ):
        """
        Initialize webhook auth dependency.
        
        Args:
            require_timestamp_validation: Whether to require timestamp validation
            log_verification_details: Whether to log verification details
        """
        self.require_timestamp_validation = require_timestamp_validation
        self.log_verification_details = log_verification_details
    
    async def __call__(
        self,
        request: Request,
        provider: str
    ) -> Dict[str, any]:
        """
        Verify webhook authentication for a specific provider.
        
        Args:
            request: The FastAPI request object
            provider: The webhook provider name
            
        Returns:
            Dictionary with verification details
            
        Raises:
            HTTPException: If authentication fails
        """
        try:
            # Validate provider
            webhook_provider = WebhookProvider(provider)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported webhook provider: {provider}"
            )
        
        # Read request body
        try:
            body = await request.body()
            payload = body.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to read webhook request body: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request body"
            )
        
        # Convert headers to dictionary
        headers = dict(request.headers)
        
        # Verify webhook signature
        try:
            is_valid, verification_details = webhook_signature_verifier.verify_webhook_request(
                payload=payload,
                headers=headers,
                provider=webhook_provider,
                validate_timestamp=self.require_timestamp_validation
            )
            
            if self.log_verification_details:
                logger.info(
                    f"Webhook verification for {provider}: "
                    f"valid={is_valid}, details={verification_details}"
                )
            
            if not is_valid:
                error_message = verification_details.get("error_message", "Signature verification failed")
                logger.warning(
                    f"Webhook signature verification failed for {provider}: {error_message}"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Webhook authentication failed: {error_message}"
                )
            
            logger.info(f"Webhook signature verified successfully for provider: {provider}")
            
            return {
                "provider": webhook_provider,
                "verification_details": verification_details,
                "payload": payload,
                "headers": headers
            }
            
        except WebhookSecurityError as e:
            logger.error(f"Webhook security error for {provider}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Webhook security error: {str(e)}"
            )
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error during webhook verification: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during webhook verification"
            )


# Global webhook auth dependency instance
webhook_auth_dependency = WebhookAuthDependency()


def get_webhook_auth(
    require_timestamp_validation: bool = True,
    log_verification_details: bool = True
) -> WebhookAuthDependency:
    """
    Factory function to create webhook auth dependency with custom settings.
    
    Args:
        require_timestamp_validation: Whether to require timestamp validation
        log_verification_details: Whether to log verification details
        
    Returns:
        WebhookAuthDependency instance
    """
    return WebhookAuthDependency(
        require_timestamp_validation=require_timestamp_validation,
        log_verification_details=log_verification_details
    )