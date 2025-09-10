"""
FastAPI application entry point for KYC/AML microservice.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware.webhook_auth import WebhookAuthenticationMiddleware
from app.api.v1 import api_router
from app.core.config import settings
from app.utils.logging import setup_logging

# Setup structured logging
setup_logging()

app = FastAPI(
    title="KYC/AML Microservice",
    description="Production-ready FastAPI microservice for KYC/AML verification workflows",
    version="0.1.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add webhook authentication middleware
app.add_middleware(
    WebhookAuthenticationMiddleware,
    webhook_paths={
        "/api/v1/webhooks/kyc/": "webhook",
        "/api/v1/webhooks/aml/": "webhook"
    },
    require_timestamp_validation=True,
    log_verification_details=True
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "kyc-aml-microservice"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)