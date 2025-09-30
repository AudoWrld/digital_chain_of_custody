from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model

User = get_user_model()

@admin.register(User)

class UserAdmin(BaseUserAdmin):
    list_display = ("email","first_name","last_name", "role", "is_active", "is_staff")
    search_fields = ("email", "first_name",  "last_name")
    ordering = ("email",)
