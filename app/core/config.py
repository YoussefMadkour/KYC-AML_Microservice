"""
Core configuration classes using Pydantic Settings.
"""
from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application
    APP_NAME: str = "KYC/AML Microservice"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development", description="Environment: development, staging, production")
    DEBUG: bool = Field(default=True, description="Enable debug mode")
    
    # Server
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8000, description="Server port")
    ALLOWED_HOSTS: List[str] = Field(default=["*"], description="Allowed CORS origins")
    
    # Database
    DATABASE_URL: str = Field(
        default="postgresql://kyc_user:kyc_password@localhost:5432/kyc_db",
        description="PostgreSQL database URL"
    )
    DATABASE_POOL_SIZE: int = Field(default=10, description="Database connection pool size")
    DATABASE_MAX_OVERFLOW: int = Field(default=20, description="Database max overflow connections")
    
    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for caching and Celery backend"
    )
    
    # RabbitMQ / Celery
    CELERY_BROKER_URL: str = Field(
        default="pyamqp://guest@localhost:5672//",
        description="Celery broker URL (RabbitMQ)"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/1",
        description="Celery result backend URL"
    )
    
    # Security
    SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production",
        description="Secret key for JWT tokens and encryption"
    )
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="JWT access token expiration")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, description="JWT refresh token expiration")
    
    # Encryption
    ENCRYPTION_KEY: Optional[str] = Field(
        default=None,
        description="Encryption key for field-level encryption (base64 encoded)"
    )
    
    # Webhook Security
    WEBHOOK_SECRET: str = Field(
        default="webhook-secret-change-in-production",
        description="Secret for webhook signature verification"
    )
    
    # Mock Provider Settings
    MOCK_PROVIDER_ENABLED: bool = Field(default=True, description="Enable mock KYC provider")
    MOCK_PROCESSING_DELAY_MIN: int = Field(default=5, description="Min processing delay in seconds")
    MOCK_PROCESSING_DELAY_MAX: int = Field(default=30, description="Max processing delay in seconds")
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(default="json", description="Log format: json or text")
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable API rate limiting")
    RATE_LIMIT_REQUESTS: int = Field(default=100, description="Requests per minute per IP")
    
    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        """Validate environment setting."""
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of: {allowed}")
        return v
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        """Validate log level setting."""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of: {allowed}")
        return v.upper()
    
    @validator("LOG_FORMAT")
    def validate_log_format(cls, v):
        """Validate log format setting."""
        allowed = ["json", "text"]
        if v not in allowed:
            raise ValueError(f"Log format must be one of: {allowed}")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()