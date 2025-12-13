from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import CustomUserChangeForm, CustomUserCreationForm
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User
    ordering = ("email",)
    list_display = ("id", "email", "name", "is_staff", "is_active")
    search_fields = ("email", "name")

    list_filter = ("is_staff", "is_active", "is_superuser", "groups")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("name",)}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login",)}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "name", "password1", "password2", "is_staff", "is_active"),
            },
        ),
    )

    filter_horizontal = (
        "groups",
        "user_permissions",
    )
