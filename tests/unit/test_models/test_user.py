"""
Unit tests for User model.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.user import User, UserRole

# Test database setup
engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(bind=engine)


@pytest.fixture
def db_session():
    """Create a test database session."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


class TestUser:
    """Test cases for User model."""

    def test_create_user(self, db_session):
        """Test creating a user."""
        user = User(
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 1),
            phone_number="1234567890",
            hashed_password="hashed_password_123",
            is_active=True,
            is_verified=False,
            role=UserRole.USER,
            address_line1="123 Main St",
            city="Anytown",
            state_province="CA",
            postal_code="12345",
            country="US",
        )

        db_session.add(user)
        db_session.commit()

        # Verify user was created
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.role == UserRole.USER
        assert user.is_active is True
        assert user.is_verified is False
        assert user.created_at is not None
        assert user.updated_at is not None

    def test_user_repr(self, db_session):
        """Test user string representation."""
        user = User(
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            hashed_password="hashed_password_123",
            role=UserRole.USER,
        )

        db_session.add(user)
        db_session.commit()

        repr_str = repr(user)
        assert "User" in repr_str
        assert str(user.id) in repr_str
        assert "test@example.com" in repr_str
        assert "USER" in repr_str

    def test_full_name_property(self):
        """Test full_name property."""
        user = User(
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            hashed_password="hashed_password_123",
        )

        assert user.full_name == "John Doe"

    def test_full_address_property(self):
        """Test full_address property."""
        # Test with complete address
        user = User(
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            hashed_password="hashed_password_123",
            address_line1="123 Main St",
            address_line2="Apt 4B",
            city="Anytown",
            state_province="CA",
            postal_code="12345",
            country="US",
        )

        expected = "123 Main St, Apt 4B, Anytown, CA, 12345, US"
        assert user.full_address == expected

        # Test with minimal address
        user_minimal = User(
            email="test2@example.com",
            first_name="Jane",
            last_name="Smith",
            hashed_password="hashed_password_123",
            address_line1="456 Oak Ave",
            city="Somewhere",
        )

        assert user_minimal.full_address == "456 Oak Ave, Somewhere"

        # Test with no address
        user_no_address = User(
            email="test3@example.com",
            first_name="Bob",
            last_name="Johnson",
            hashed_password="hashed_password_123",
        )

        assert user_no_address.full_address is None

    def test_has_role_method(self):
        """Test has_role method."""
        user = User(
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            hashed_password="hashed_password_123",
            role=UserRole.ADMIN,
        )

        assert user.has_role(UserRole.ADMIN) is True
        assert user.has_role(UserRole.USER) is False
        assert user.has_role(UserRole.COMPLIANCE_OFFICER) is False

    def test_is_admin_method(self):
        """Test is_admin method."""
        admin_user = User(
            email="admin@example.com",
            first_name="Admin",
            last_name="User",
            hashed_password="hashed_password_123",
            role=UserRole.ADMIN,
        )

        regular_user = User(
            email="user@example.com",
            first_name="Regular",
            last_name="User",
            hashed_password="hashed_password_123",
            role=UserRole.USER,
        )

        assert admin_user.is_admin() is True
        assert regular_user.is_admin() is False

    def test_is_compliance_officer_method(self):
        """Test is_compliance_officer method."""
        compliance_user = User(
            email="compliance@example.com",
            first_name="Compliance",
            last_name="Officer",
            hashed_password="hashed_password_123",
            role=UserRole.COMPLIANCE_OFFICER,
        )

        regular_user = User(
            email="user@example.com",
            first_name="Regular",
            last_name="User",
            hashed_password="hashed_password_123",
            role=UserRole.USER,
        )

        assert compliance_user.is_compliance_officer() is True
        assert regular_user.is_compliance_officer() is False

    def test_user_role_enum(self):
        """Test UserRole enum values."""
        assert UserRole.USER == "user"
        assert UserRole.ADMIN == "admin"
        assert UserRole.COMPLIANCE_OFFICER == "compliance_officer"

    def test_unique_email_constraint(self, db_session):
        """Test that email must be unique."""
        user1 = User(
            email="unique@example.com",
            first_name="First",
            last_name="User",
            hashed_password="hashed_password_123",
        )

        user2 = User(
            email="unique@example.com",  # Same email
            first_name="Second",
            last_name="User",
            hashed_password="hashed_password_456",
        )

        db_session.add(user1)
        db_session.commit()

        db_session.add(user2)

        # Should raise an integrity error due to unique constraint
        with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
            db_session.commit()

    def test_default_values(self, db_session):
        """Test default values for user fields."""
        user = User(
            email="defaults@example.com",
            first_name="Default",
            last_name="User",
            hashed_password="hashed_password_123",
        )

        db_session.add(user)
        db_session.commit()

        # Check default values
        assert user.is_active is True
        assert user.is_verified is False
        assert user.role == UserRole.USER
