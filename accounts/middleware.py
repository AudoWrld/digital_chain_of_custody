from django.shortcuts import redirect
from django.urls import reverse


class Enforce2FAMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if not request.user.verified:
                # Allow access to verification pages
                allowed_verification_paths = [
                    '/accounts/verification-sent',
                    '/accounts/resend_verification',
                    '/accounts/register',
                    '/accounts/login',
                ]
                if request.path.startswith('/accounts/verify/') or request.path in allowed_verification_paths:
                    pass  # Allow
                else:
                    request.session["pending_verification_email"] = request.user.email
                    return redirect('verification_sent')
            else:
                if request.user.is_superuser:
                    if not request.user.two_factor_enabled:
                        # Allow access to 2FA setup pages and logout
                        allowed_paths = [
                            reverse('accounts:second_authentication'),
                            reverse('accounts:recovery_codes_view'),
                            reverse('accounts:download_recovery_codes'),
                            reverse('accounts:setup_new_2fa'),
                            reverse('accounts:logout'),
                        ]
                        if request.path not in allowed_paths and not request.path.startswith('/admin/login/'):
                            return redirect('accounts:second_authentication')
        response = self.get_response(request)
        return response