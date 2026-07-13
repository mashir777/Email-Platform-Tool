from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, UserRole


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "email",
        "username",
        "first_name",
        "last_name",
        "role",
        "is_staff",
        "is_active",
        "is_verified",
        "created_at",
    )
    list_filter = ("role", "is_staff", "is_active", "is_verified", "is_superuser")
    search_fields = ("email", "username", "first_name", "last_name", "company_name")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at", "updated_at", "last_login", "date_joined")

    fieldsets = UserAdmin.fieldsets + (
        (
            "Platform Profile",
            {
                "fields": (
                    "id",
                    "role",
                    "phone",
                    "company_name",
                    "timezone",
                    "avatar",
                    "is_verified",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Platform Profile",
            {
                "fields": (
                    "email",
                    "role",
                    "phone",
                    "company_name",
                    "timezone",
                ),
            },
        ),
    )

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == "role":
            kwargs["choices"] = UserRole.choices
        return super().formfield_for_choice_field(db_field, request, **kwargs)
