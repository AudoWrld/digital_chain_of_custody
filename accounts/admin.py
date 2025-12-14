from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from .tokens import account_activation_token
from django.utils.encoding import force_bytes
from django.conf import settings

User = get_user_model()

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "first_name", "last_name", "role", "is_active", "verified", "two_factor_enabled", "is_staff")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('role', 'verified', 'two_factor_enabled', 'two_factor_secret', 'recovery_codes')}),
    )

    def save_model(self, request, obj, form, change):
        if not change:  # New user
            obj.is_active = False
            obj.verified = False
            obj.two_factor_enabled = False
            obj.set_password(form.cleaned_data.get('password1'))  # Assuming password1 is the field
            super().save_model(request, obj, form, change)
            # Send verification email
            current_site = get_current_site(request)
            subject = "Verify your email"
            uid = urlsafe_base64_encode(force_bytes(obj.pk))
            token = account_activation_token.make_token(obj)
            protocol = "https" if request.is_secure() else "http"
            message = render_to_string(
                "emails/verification_email.html",
                {
                    "user": obj,
                    "domain": current_site.domain,
                    "protocol": protocol,
                    "uid": uid,
                    "token": token,
                },
            )
            send_mail(
                subject,
                message,
                settings.EMAIL_HOST_USER,
                [obj.email],
                fail_silently=False,
            )
        else:
            super().save_model(request, obj, form, change)
