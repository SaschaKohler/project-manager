"""
Tests for tenant models (Organization, Membership, OrganizationInvitation).
"""

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.tenants.models import Organization, Membership, OrganizationInvitation


class TestOrganization:
    """Test cases for Organization model."""
    
    def test_create_organization(self, organization_factory):
        """Test creating a basic organization."""
        org = organization_factory(slug="test-org")

        assert org.name == "Test Org"
        assert org.slug == "test-org"
        assert org.pk is not None
        assert str(org) == "Test Org"
    
    def test_organization_slug_unique(self, db):
        """Test that organization slugs must be unique."""
        Organization.objects.create(name="Org 1", slug="same-slug")
        
        with pytest.raises(Exception):  # Should raise IntegrityError
            Organization.objects.create(name="Org 2", slug="same-slug")
    
    def test_organization_str_representation(self, organization_factory):
        """Test string representation of organization."""
        org = organization_factory(name="My Organization")
        assert str(org) == "My Organization"


class TestMembership:
    """Test cases for Membership model."""
    
    def test_create_membership(self, organization_factory, user_factory):
        """Test creating a membership."""
        org = organization_factory()
        user = user_factory()
        
        membership = Membership.objects.create(
            organization=org,
            user=user,
            role=Membership.Role.MEMBER
        )
        
        assert membership.organization == org
        assert membership.user == user
        assert membership.role == Membership.Role.MEMBER
        assert str(membership) == f"{user.id} in {org.id}"
    
    def test_membership_unique_constraint(self, db, organization_factory, user_factory):
        """Test that a user can only have one membership per organization."""
        org = organization_factory()
        user = user_factory()
        
        # Create first membership
        Membership.objects.create(
            organization=org,
            user=user,
            role=Membership.Role.MEMBER
        )
        
        # Attempt to create duplicate should fail
        with pytest.raises(Exception):  # IntegrityError
            Membership.objects.create(
                organization=org,
                user=user,
                role=Membership.Role.ADMIN
            )
    
    def test_membership_roles(self, organization_factory, user_factory):
        """Test different membership roles."""
        org = organization_factory()
        
        for role_choice in Membership.Role:
            user = user_factory(email=f"test-{role_choice.value}@example.com")
            membership = Membership.objects.create(
                organization=org,
                user=user,
                role=role_choice
            )
            assert membership.role == role_choice
    
    def test_membership_str_representation(self, organization_factory, user_factory):
        """Test string representation of membership."""
        org = organization_factory(name="Test Org")
        user = user_factory(email="test@example.com")
        
        membership = Membership.objects.create(
            organization=org,
            user=user,
            role=Membership.Role.ADMIN
        )
        
        expected_str = f"{user.id} in {org.id}"
        assert str(membership) == expected_str


class TestOrganizationInvitation:
    """Test cases for OrganizationInvitation model."""
    
    def test_create_invitation(self, organization_factory, user_factory):
        """Test creating an organization invitation."""
        org = organization_factory()
        inviter = user_factory()
        
        invitation = OrganizationInvitation.objects.create(
            organization=org,
            email="newuser@example.com",
            role=Membership.Role.MEMBER,
            invited_by=inviter
        )
        
        assert invitation.organization == org
        assert invitation.email == "newuser@example.com"
        assert invitation.role == Membership.Role.MEMBER
        assert invitation.invited_by == inviter
        assert invitation.status == OrganizationInvitation.Status.PENDING
        assert invitation.token is not None
        assert invitation.is_expired() is False
    
    def test_invitation_status_choices(self, organization_factory, user_factory):
        """Test different invitation statuses."""
        org = organization_factory()
        inviter = user_factory()
        
        for status_choice in OrganizationInvitation.Status:
            invitation = OrganizationInvitation.objects.create(
                organization=org,
                email=f"user-{status_choice.value}@example.com",
                role=Membership.Role.MEMBER,
                invited_by=inviter,
                status=status_choice
            )
            assert invitation.status == status_choice
    
    def test_invitation_expiry(self, organization_factory, user_factory):
        """Test invitation expiry functionality."""
        org = organization_factory()
        inviter = user_factory()
        
        # Invitation without expiry date
        invitation_no_expiry = OrganizationInvitation.objects.create(
            organization=org,
            email="no-expiry@example.com",
            invited_by=inviter,
            expires_at=None
        )
        assert invitation_no_expiry.is_expired() is False
        
        # Expired invitation
        past_date = timezone.now() - timezone.timedelta(days=1)
        invitation_expired = OrganizationInvitation.objects.create(
            organization=org,
            email="expired@example.com",
            invited_by=inviter,
            expires_at=past_date
        )
        assert invitation_expired.is_expired() is True
        
        # Future invitation
        future_date = timezone.now() + timezone.timedelta(days=1)
        invitation_future = OrganizationInvitation.objects.create(
            organization=org,
            email="future@example.com",
            invited_by=inviter,
            expires_at=future_date
        )
        assert invitation_future.is_expired() is False
    
    def test_invitation_unique_token(self, db):
        """Test that invitation tokens are unique."""
        from apps.tenants.models import Organization, OrganizationInvitation
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        org = Organization.objects.create(name="Test Org", slug="test-org")
        inviter = User.objects.create_user(
            "inviter@example.com",
            "testpass123"
        )
        
        # Create first invitation
        invitation1 = OrganizationInvitation.objects.create(
            organization=org,
            email="user1@example.com",
            invited_by=inviter
        )
        
        # Create second invitation (should get different token)
        invitation2 = OrganizationInvitation.objects.create(
            organization=org,
            email="user2@example.com",
            invited_by=inviter
        )
        
        assert invitation1.token != invitation2.token