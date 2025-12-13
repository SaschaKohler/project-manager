from rest_framework import serializers

from .models import Membership, Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ("id", "name", "slug", "created_at")
        read_only_fields = ("id", "created_at")


class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ("id", "organization", "user", "role", "created_at")
        read_only_fields = ("id", "created_at")
