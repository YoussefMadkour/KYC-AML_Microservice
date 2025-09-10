"""
User model with encrypted fields for sensitive data.
"""

from datetime import date
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Column, Date
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import String
from sqlalchemy.orm import relationship

from app.models.base import BaseModel
from app.utils.encryption import EncryptedType


class UserRole(str, Enum):
    """User role enumeration."""

    USER = "user"
    ADMIN = "admin"
    COMPLIANCE_OFFICER = "compliance_officer"


class User(BaseModel):
    """User model with encrypted sensitive fields."""

    __tablename__ = "users"

    # Basic information
    email = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        doc="User email address (unique identifier)",
    )

    first_name = Column(String(100), nullable=False, doc="User's first name")

    last_name = Column(String(100), nullable=False, doc="User's last name")

    date_of_birth = Column(Date, nullable=True, doc="User's date of birth")

    # Encrypted sensitive fields
    phone_number = Column(
        EncryptedType(255), nullable=True, doc="Encrypted phone number"
    )

    # Authentication
    hashed_password = Column(
        String(255), nullable=False, doc="Hashed password using bcrypt"
    )

    # Status and role
    is_active = Column(
        Boolean, default=True, nullable=False, doc="Whether the user account is active"
    )

    is_verified = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether the user's email is verified",
    )

    role = Column(
        SQLEnum(UserRole),
        default=UserRole.USER,
        nullable=False,
        doc="User's role in the system",
    )

    # Address information (could be encrypted in production)
    address_line1 = Column(String(255), nullable=True, doc="Primary address line")

    address_line2 = Column(String(255), nullable=True, doc="Secondary address line")

    city = Column(String(100), nullable=True, doc="City")

    state_province = Column(String(100), nullable=True, doc="State or province")

    postal_code = Column(String(20), nullable=True, doc="Postal or ZIP code")

    country = Column(String(2), nullable=True, doc="ISO 3166-1 alpha-2 country code")

    # Relationships
    kyc_checks = relationship(
        "KYCCheck",
        back_populates="user",
        cascade="all, delete-orphan",
        doc="User's KYC verification checks",
    )

    def __repr__(self) -> str:
        """String representation of the user."""
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        return f"{self.first_name} {self.last_name}"

    @property
    def full_address(self) -> Optional[str]:
        """Get formatted full address."""
        if not self.address_line1:
            return None

        parts = [self.address_line1]
        if self.address_line2:
            parts.append(self.address_line2)
        if self.city:
            parts.append(self.city)
        if self.state_province:
            parts.append(self.state_province)
        if self.postal_code:
            parts.append(self.postal_code)
        if self.country:
            parts.append(self.country.upper())

        return ", ".join(parts)

    def has_role(self, role: UserRole) -> bool:
        """Check if user has a specific role."""
        return self.role == role

    def is_admin(self) -> bool:
        """Check if user is an admin."""
        return self.role == UserRole.ADMIN

    def is_compliance_officer(self) -> bool:
        """Check if user is a compliance officer."""
        return self.role == UserRole.COMPLIANCE_OFFICER
