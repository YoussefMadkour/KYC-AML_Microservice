"""
Unit tests for webhook authentication middleware.
"""
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.testclient import TestClient

from app.api.middleware.webhook_auth import (
    WebhookAuthenticationMiddleware,
    WebhookAuthDependency,
    webhook_auth_dependency,
    get_webhook_auth
)
from app.utils.webhook_security import WebhookProvider, generate_webhook_signature


class TestWebhookAuthenticationMiddleware:
    """Test cases for WebhookAuthenticationMiddleware."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI()
        self.test_payload = '{"status": "approved", "kyc_id": "kyc_123"}'
        
        # Add test webhook endpoint
        @self.app.post("/webhooks/kyc/{provider}")
        async def webhook_handler(provider: str, request: Request):
            body = await request.body()
            return {
                "provider": provider,
                "payload": body.decode('utf-8'),
                "verified": getattr(request.state, 'webhook_verified', False)
            }
        
        # Add non-webhook endpoint
        @self.app.get("/health")
        async def health_check():
            return {"status": "ok"}
    
    def test_middleware_initialization_default(self):
        """Test middleware initialization with default settings."""
        middleware = WebhookAuthenticationMiddleware(self.app)
        
        assert middleware.webhook_paths is not None
        assert "/webhooks/kyc/" in middleware.webhook_paths
        assert "/webhooks/aml/" in middleware.webhook_paths
        assert middleware.require_timestamp_validation is True
        assert middleware.log_verification_details is True
    
    def test_middleware_initialization_custom(self):
        """Test middleware initialization with custom settings."""
        custom_paths = {"/custom/webhook/": "webhook"}
        
        middleware = WebhookAuthenticationMiddleware(
            self.app,
            webhook_paths=custom_paths,
            require_timestamp_validation=False,
            log_verification_details=False
        )
        
        assert middleware.webhook_paths == custom_paths
        assert middleware.require_timestamp_validation is False
        assert middleware.log_verification_details is False
    
    def test_is_webhook_request_true(self):
        """Test _is_webhook_request returns True for webhook paths."""
        middleware = WebhookAuthenticationMiddleware(self.app)
        
        # Mock request
        request = MagicMock()
        request.url.path = "/webhooks/kyc/mock_provider_1"
        request.method = "POST"
        
        result = middleware._is_webhook_request(request)
        assert result is True
    
    def test_is_webhook_request_false_method(self):
        """Test _is_webhook_request returns False for non-POST methods."""
        middleware = WebhookAuthenticationMiddleware(self.app)
        
        # Mock request with GET method
        request = MagicMock()
        request.url.path = "/webhooks/kyc/mock_provider_1"
        request.method = "GET"
        
        result = middleware._is_webhook_request(request)
        assert result is False
    
    def test_is_webhook_request_false_path(self):
        """Test _is_webhook_request returns False for non-webhook paths."""
        middleware = WebhookAuthenticationMiddleware(self.app)
        
        # Mock request with non-webhook path
        request = MagicMock()
        request.url.path = "/api/users"
        request.method = "POST"
        
        result = middleware._is_webhook_request(request)
        assert result is False
    
    def test_extract_provider_from_path_kyc(self):
        """Test extracting provider from KYC webhook path."""
        middleware = WebhookAuthenticationMiddleware(self.app)
        
        path = "/webhooks/kyc/mock_provider_1"
        provider = middleware._extract_provider_from_path(path)
        
        assert provider == WebhookProvider.MOCK_PROVIDER_1
    
    def test_extract_provider_from_path_aml(self):
        """Test extracting provider from AML webhook path."""
        middleware = WebhookAuthenticationMiddleware(self.app)
        
        path = "/webhooks/aml/jumio"
        provider = middleware._extract_provider_from_path(path)
        
        assert provider == WebhookProvider.JUMIO
    
    def test_extract_provider_from_path_api_v1(self):
        """Test extracting provider from API v1 webhook path."""
        middleware = WebhookAuthenticationMiddleware(self.app)
        
        path = "/api/v1/webhooks/kyc/onfido"
        provider = middleware._extract_provider_from_path(path)
        
        assert provider == WebhookProvider.ONFIDO
    
    def test_extract_provider_from_path_invalid(self):
        """Test extracting provider from invalid path."""
        middleware = WebhookAuthenticationMiddleware(self.app)
        
        path = "/webhooks/kyc/invalid_provider"
        provider = middleware._extract_provider_from_path(path)
        
        assert provider is None
    
    def test_extract_provider_from_path_malformed(self):
        """Test extracting provider from malformed path."""
        middleware = WebhookAuthenticationMiddleware(self.app)
        
        path = "/invalid/path"
        provider = middleware._extract_provider_from_path(path)
        
        assert provider is None
    
    @pytest.mark.asyncio
    async def test_dispatch_non_webhook_request(self):
        """Test middleware dispatch for non-webhook requests."""
        middleware = WebhookAuthenticationMiddleware(self.app)
        
        # Mock non-webhook request
        request = MagicMock()
        request.url.path = "/health"
        request.method = "GET"
        
        # Mock call_next
        call_next = AsyncMock()
        expected_response = MagicMock()
        call_next.return_value = expected_response
        
        result = await middleware.dispatch(request, call_next)
        
        # Should call next middleware without authentication
        call_next.assert_called_once_with(request)
        assert result == expected_response
    
    @pytest.mark.asyncio
    async def test_dispatch_webhook_request_no_provider(self):
        """Test middleware dispatch for webhook request without valid provider."""
        middleware = WebhookAuthenticationMiddleware(self.app)
        
        # Mock webhook request with invalid provider
        request = MagicMock()
        request.url.path = "/webhooks/kyc/invalid_provider"
        request.method = "POST"
        
        call_next = AsyncMock()
        
        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, call_next)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "provider not specified" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_dispatch_webhook_request_body_error(self):
        """Test middleware dispatch when request body cannot be read."""
        middleware = WebhookAuthenticationMiddleware(self.app)
        
        # Mock webhook request
        request = MagicMock()
        request.url.path = "/webhooks/kyc/mock_provider_1"
        request.method = "POST"
        request.body = AsyncMock(side_effect=Exception("Body read error"))
        
        call_next = AsyncMock()
        
        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, call_next)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid request body" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_dispatch_webhook_request_success(self):
        """Test successful webhook request dispatch."""
        middleware = WebhookAuthenticationMiddleware(self.app)
        
        # Generate valid signature
        provider = WebhookProvider.MOCK_PROVIDER_1
        signature = generate_webhook_signature(self.test_payload, provider)
        
        # Mock webhook request
        request = MagicMock()
        request.url.path = "/webhooks/kyc/mock_provider_1"
        request.method = "POST"
        request.body = AsyncMock(return_value=self.test_payload.encode('utf-8'))
        request.headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature
        }
        request.state = MagicMock()
        
        # Mock call_next
        call_next = AsyncMock()
        expected_response = MagicMock()
        call_next.return_value = expected_response
        
        with patch('app.api.middleware.webhook_auth.webhook_signature_verifier') as mock_verifier:
            mock_verifier.verify_webhook_request.return_value = (
                True,
                {
                    "signature_valid": True,
                    "timestamp_valid": True,
                    "signature_found": True,
                    "timestamp_found": False,
                    "error_message": None
                }
            )
            
            result = await middleware.dispatch(request, call_next)
        
        # Should set request state
        assert request.state.webhook_verified is True
        assert request.state.webhook_provider == provider
        assert request.state.webhook_verification_details is not None
        
        # Should call next middleware
        call_next.assert_called_once_with(request)
        assert result == expected_response
    
    @pytest.mark.asyncio
    async def test_dispatch_webhook_request_invalid_signature(self):
        """Test webhook request dispatch with invalid signature."""
        middleware = WebhookAuthenticationMiddleware(self.app)
        
        # Mock webhook request
        request = MagicMock()
        request.url.path = "/webhooks/kyc/mock_provider_1"
        request.method = "POST"
        request.body = AsyncMock(return_value=self.test_payload.encode('utf-8'))
        request.headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": "sha256=invalid_signature"
        }
        
        call_next = AsyncMock()
        
        with patch('app.api.middleware.webhook_auth.webhook_signature_verifier') as mock_verifier:
            mock_verifier.verify_webhook_request.return_value = (
                False,
                {
                    "signature_valid": False,
                    "timestamp_valid": True,
                    "signature_found": True,
                    "timestamp_found": False,
                    "error_message": "Invalid signature"
                }
            )
            
            with pytest.raises(HTTPException) as exc_info:
                await middleware.dispatch(request, call_next)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Webhook authentication failed" in exc_info.value.detail


class TestWebhookAuthDependency:
    """Test cases for WebhookAuthDependency."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.test_payload = '{"status": "approved", "kyc_id": "kyc_123"}'
        self.provider = "mock_provider_1"
    
    def test_dependency_initialization_default(self):
        """Test dependency initialization with default settings."""
        dependency = WebhookAuthDependency()
        
        assert dependency.require_timestamp_validation is True
        assert dependency.log_verification_details is True
    
    def test_dependency_initialization_custom(self):
        """Test dependency initialization with custom settings."""
        dependency = WebhookAuthDependency(
            require_timestamp_validation=False,
            log_verification_details=False
        )
        
        assert dependency.require_timestamp_validation is False
        assert dependency.log_verification_details is False
    
    @pytest.mark.asyncio
    async def test_call_invalid_provider(self):
        """Test dependency call with invalid provider."""
        dependency = WebhookAuthDependency()
        
        # Mock request
        request = MagicMock()
        request.body = AsyncMock(return_value=self.test_payload.encode('utf-8'))
        
        with pytest.raises(HTTPException) as exc_info:
            await dependency(request, "invalid_provider")
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unsupported webhook provider" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_call_body_read_error(self):
        """Test dependency call when request body cannot be read."""
        dependency = WebhookAuthDependency()
        
        # Mock request with body read error
        request = MagicMock()
        request.body = AsyncMock(side_effect=Exception("Body read error"))
        
        with pytest.raises(HTTPException) as exc_info:
            await dependency(request, self.provider)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid request body" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_call_success(self):
        """Test successful dependency call."""
        dependency = WebhookAuthDependency()
        
        # Generate valid signature
        provider_enum = WebhookProvider.MOCK_PROVIDER_1
        signature = generate_webhook_signature(self.test_payload, provider_enum)
        
        # Mock request
        request = MagicMock()
        request.body = AsyncMock(return_value=self.test_payload.encode('utf-8'))
        request.headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature
        }
        
        with patch('app.api.middleware.webhook_auth.webhook_signature_verifier') as mock_verifier:
            mock_verifier.verify_webhook_request.return_value = (
                True,
                {
                    "signature_valid": True,
                    "timestamp_valid": True,
                    "signature_found": True,
                    "timestamp_found": False,
                    "error_message": None
                }
            )
            
            result = await dependency(request, self.provider)
        
        assert result["provider"] == provider_enum
        assert result["payload"] == self.test_payload
        assert result["headers"]["Content-Type"] == "application/json"
        assert result["verification_details"]["signature_valid"] is True
    
    @pytest.mark.asyncio
    async def test_call_verification_failure(self):
        """Test dependency call with verification failure."""
        dependency = WebhookAuthDependency()
        
        # Mock request
        request = MagicMock()
        request.body = AsyncMock(return_value=self.test_payload.encode('utf-8'))
        request.headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": "sha256=invalid_signature"
        }
        
        with patch('app.api.middleware.webhook_auth.webhook_signature_verifier') as mock_verifier:
            mock_verifier.verify_webhook_request.return_value = (
                False,
                {
                    "signature_valid": False,
                    "timestamp_valid": True,
                    "signature_found": True,
                    "timestamp_found": False,
                    "error_message": "Invalid signature"
                }
            )
            
            with pytest.raises(HTTPException) as exc_info:
                await dependency(request, self.provider)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Webhook authentication failed" in exc_info.value.detail


class TestConvenienceFunctions:
    """Test cases for convenience functions and global instances."""
    
    def test_webhook_auth_dependency_global(self):
        """Test global webhook_auth_dependency instance."""
        assert webhook_auth_dependency is not None
        assert isinstance(webhook_auth_dependency, WebhookAuthDependency)
        assert webhook_auth_dependency.require_timestamp_validation is True
        assert webhook_auth_dependency.log_verification_details is True
    
    def test_get_webhook_auth_factory(self):
        """Test get_webhook_auth factory function."""
        dependency = get_webhook_auth(
            require_timestamp_validation=False,
            log_verification_details=False
        )
        
        assert isinstance(dependency, WebhookAuthDependency)
        assert dependency.require_timestamp_validation is False
        assert dependency.log_verification_details is False
    
    def test_get_webhook_auth_factory_defaults(self):
        """Test get_webhook_auth factory function with defaults."""
        dependency = get_webhook_auth()
        
        assert isinstance(dependency, WebhookAuthDependency)
        assert dependency.require_timestamp_validation is True
        assert dependency.log_verification_details is True


class TestIntegrationWithFastAPI:
    """Integration tests with FastAPI application."""
    
    def setup_method(self):
        """Set up test FastAPI application."""
        self.app = FastAPI()
        
        # Add middleware
        self.app.add_middleware(
            WebhookAuthenticationMiddleware,
            require_timestamp_validation=False  # Disable for easier testing
        )
        
        # Add webhook endpoint
        @self.app.post("/webhooks/kyc/{provider}")
        async def webhook_handler(provider: str, request: Request):
            body = await request.body()
            return {
                "provider": provider,
                "payload": body.decode('utf-8'),
                "verified": getattr(request.state, 'webhook_verified', False),
                "verification_details": getattr(request.state, 'webhook_verification_details', None)
            }
        
        # Add non-webhook endpoint
        @self.app.get("/health")
        async def health_check():
            return {"status": "ok"}
        
        self.client = TestClient(self.app)
        self.test_payload = '{"status": "approved", "kyc_id": "kyc_123"}'
    
    def test_non_webhook_endpoint_no_auth(self):
        """Test that non-webhook endpoints are not authenticated."""
        response = self.client.get("/health")
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    def test_webhook_endpoint_valid_signature(self):
        """Test webhook endpoint with valid signature."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        signature = generate_webhook_signature(self.test_payload, provider)
        
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature
        }
        
        response = self.client.post(
            "/webhooks/kyc/mock_provider_1",
            data=self.test_payload,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "mock_provider_1"
        assert data["payload"] == self.test_payload
        assert data["verified"] is True
        assert data["verification_details"]["signature_valid"] is True