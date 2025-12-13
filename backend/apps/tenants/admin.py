from django.contrib import admin

from .models import Membership, Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "created_at")
    search_fields = ("name", "slug")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "user", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("organization__name", "user__email")
