"""
User request and response schemas.
"""
from datetime import date
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator

from app.models.user import UserRole


class UserBase(BaseModel):
    """Base user schema with common fields."""
    
    email: EmailStr = Field(..., description="User email address")
    first_name: str = Field(..., min_length=1, max_length=100, description="First name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Last name")


class UserCreate(UserBase):
    """User creation schema."""
    
    password: str = Field(..., min_length=8, description="User password")
    date_of_birth: Optional[date] = Field(None, description="Date of birth")
    phone_number: Optional[str] = Field(None, description="Phone number")
    role: UserRole = Field(default=UserRole.USER, description="User role")
    
    @validator("password")
    def validate_password_strength(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        
        if not (has_upper and has_lower and has_digit):
            raise ValueError(
                "Password must contain at least one uppercase letter, "
                "one lowercase letter, and one digit"
            )
        
        return v


class UserUpdate(BaseModel):
    """User update schema."""
    
    first_name: Optional[str] = Field(None, min_length=1, max_length=100, description="First name")
    last_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Last name")
    date_of_birth: Optional[date] = Field(None, description="Date of birth")
    phone_number: Optional[str] = Field(None, description="Phone number")
    address_line1: Optional[str] = Field(None, max_length=255, description="Address line 1")
    address_line2: Optional[str] = Field(None, max_length=255, description="Address line 2")
    city: Optional[str] = Field(None, max_length=100, description="City")
    state_province: Optional[str] = Field(None, max_length=100, description="State/Province")
    postal_code: Optional[str] = Field(None, max_length=20, description="Postal code")
    country: Optional[str] = Field(None, max_length=2, description="Country code (ISO 3166-1 alpha-2)")
    
    @validator("country")
    def validate_country_code(cls, v):
        """Validate country code format."""
        if v and len(v) != 2:
            raise ValueError("Country code must be 2 characters (ISO 3166-1 alpha-2)")
        return v.upper() if v else v


class UserResponse(UserBase):
    """User response schema."""
    
    id: str = Field(..., description="User ID")
    date_of_birth: Optional[date] = Field(None, description="Date of birth")
    phone_number: Optional[str] = Field(None, description="Phone number")
    role: UserRole = Field(..., description="User role")
    is_active: bool = Field(..., description="Whether user is active")
    is_verified: bool = Field(..., description="Whether user email is verified")
    address_line1: Optional[str] = Field(None, description="Address line 1")
    address_line2: Optional[str] = Field(None, description="Address line 2")
    city: Optional[str] = Field(None, description="City")
    state_province: Optional[str] = Field(None, description="State/Province")
    postal_code: Optional[str] = Field(None, description="Postal code")
    country: Optional[str] = Field(None, description="Country code")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class UserProfile(UserResponse):
    """Extended user profile schema."""
    
    full_name: str = Field(..., description="Full name")
    full_address: Optional[str] = Field(None, description="Formatted full address")
    
    class Config:
        from_attributes = True


class UserAdminUpdate(UserUpdate):
    """Admin user update schema with additional fields."""
    
    email: Optional[EmailStr] = Field(None, description="User email address")
    role: Optional[UserRole] = Field(None, description="User role")
    is_active: Optional[bool] = Field(None, description="Whether user is active")
    is_verified: Optional[bool] = Field(None, description="Whether user email is verified")