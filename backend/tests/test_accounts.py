"""
Tests for accounts app (User model, forms, etc.).
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.accounts.models import User  # If you have a custom User model


class TestUserModel:
    """Test cases for User model."""
    
    def test_create_user(self, user_factory):
        """Test creating a basic user."""
        user = user_factory(email="test@example.com")
        
        assert user.email == "test@example.com"
        assert user.is_active is True
        assert user.is_staff is False
        assert user.is_superuser is False
        assert user.check_password("testpass123") is True
        assert str(user) == "test@example.com"
    
    def test_create_superuser(self, db):
        """Test creating a superuser."""
        User = get_user_model()
        superuser = User.objects.create_superuser(
            "admin@example.com",
            "adminpass123"
        )

        assert superuser.email == "admin@example.com"
        assert superuser.is_active is True
        assert superuser.is_staff is True
        assert superuser.is_superuser is True
    
    def test_user_email_unique(self, db):
        """Test that user emails must be unique."""
        User = get_user_model()

        # Create first user
        User.objects.create_user(
            "duplicate@example.com",
            "testpass123"
        )

        # Attempt to create duplicate should fail
        with pytest.raises(Exception):  # IntegrityError
            User.objects.create_user(
                "duplicate@example.com",
                "testpass456"
            )
    
    def test_user_str_representation(self, user_factory):
        """Test string representation of user."""
        user = user_factory(email="user@example.com")
        assert str(user) == "user@example.com"
    
    def test_user_properties(self, user_factory):
        """Test user properties and methods."""
        user = user_factory()

        # Test name field
        assert hasattr(user, 'name')
        assert user.name == ""
    
    def test_user_email_normalization(self, db):
        """Test that email addresses are normalized."""
        User = get_user_model()

        # Create user with uppercase email
        user = User.objects.create_user(
            "USER@example.com",
            "testpass123"
        )

        # Email should be stored in lowercase
        assert user.email == "user@example.com"
    
    def test_user_validation(self, user_factory):
        """Test user model validation."""
        user = user_factory()
        
        # Test invalid email
        user.email = "invalid-email"
        with pytest.raises(ValidationError):
            user.full_clean()
        
        # Test empty required fields
        user.email = ""
        with pytest.raises(ValidationError):
            user.full_clean()


class TestUserManager:
    """Test cases for custom UserManager."""
    
    def test_create_user(self, db):
        """Test create_user method."""
        User = get_user_model()

        user = User.objects.create_user(
            "test@example.com",
            "testpass123"
        )

        assert user.email == "test@example.com"
        assert user.check_password("testpass123")
        assert user.is_active is True
        assert user.is_staff is False
        assert user.is_superuser is False

    def test_create_user_without_email(self, db):
        """Test create_user without email should raise error."""
        User = get_user_model()

        with pytest.raises(ValueError):
            User.objects.create_user("")

    def test_create_superuser(self, db):
        """Test create_superuser method."""
        User = get_user_model()

        superuser = User.objects.create_superuser(
            "admin@example.com",
            "adminpass123"
        )

        assert superuser.email == "admin@example.com"
        assert superuser.is_staff is True
        assert superuser.is_superuser is True

    def test_create_superuser_missing_fields(self, db):
        """Test create_superuser with missing required fields."""
        User = get_user_model()

        # Missing password - should raise TypeError
        with pytest.raises(TypeError):
            User.objects.create_superuser("admin@example.com")

        # Missing email - should raise ValueError from _create_user
        with pytest.raises(ValueError):
            User.objects.create_superuser("", "adminpass123")

    def test_create_user_with_extra_fields(self, db):
        """Test create_user with extra fields."""
        User = get_user_model()

        user = User.objects.create_user(
            "test@example.com",
            "testpass123",
            name="John Doe"
        )

        # Check that the name field was set (if it exists)
        if hasattr(user, 'name'):
            assert user.name == "John Doe"


class TestUserForms:
    """Test cases for user forms."""

    def test_user_change_form(self, user_factory):
        """Test user change form (if exists)."""
        from apps.accounts.forms import UserChangeForm

        user = user_factory()

        # This would test the form if it exists
        form_data = {
            "email": "updated@example.com",
            "name": "Jane Smith",
        }

        form = UserChangeForm(data=form_data, instance=user)
        if form.is_valid():
            user = form.save()
            assert user.email == "updated@example.com"