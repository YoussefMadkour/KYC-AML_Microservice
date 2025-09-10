"""
API version 1 router configuration.
"""

from fastapi import APIRouter

from app.api.v1 import auth, gdpr, kyc, users, webhooks

api_router = APIRouter()

# Include authentication routes
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])

# Include user management routes
api_router.include_router(users.router, prefix="/users", tags=["users"])

# Include KYC verification routes
api_router.include_router(kyc.router, prefix="/kyc", tags=["kyc"])

# Include webhook routes
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

# Include GDPR compliance routes
api_router.include_router(gdpr.router, tags=["gdpr"])
