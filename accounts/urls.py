from django.urls import path, include
from . import views

app_name = 'accounts'

urlpatterns = [
    path("login", views.login_view, name="login"),
    path("register", views.register, name="register"),
    path("verification-sent", views.verification_sent, name="verification_sent"),
    path("setup-your-2fa", views.second_authentication, name="second_authentication"),
    path("recovery-codes/", views.recovery_codes_view, name="recovery_codes_view"),
    path(
        "download-recovery-codes/",
        views.download_recovery_codes,
        name="download_recovery_codes",
    ),
    path(
        "verify-recovery-code/", views.verify_recovery_code, name="verify_recovery_code"
    ),
    path(
        "proceed-to-dashboard", views.proceed_to_dashboard, name="proceed_to_dashboard"
    ),
    path("setup-new-2fa", views.setup_new_2fa, name="setup_new_2fa"),
    path("verify/<uidb64>/<token>/", views.verify_email, name="verify_email"),
    path(
        "resend_verification",
        views.resend_verification_email,
        name="resend_verification",
    ),
    path("logout", views.logout_view, name="logout"),
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("reset/<uidb64>/<token>/", views.reset_password, name="reset_password"),
    path("management/", views.user_management, name="user_management"),
    path("management/list/", views.user_list, name="user_list"),
    path("management/detail/<int:user_id>/", views.user_detail, name="user_detail"),
    path("management/toggle-status/<int:user_id>/", views.toggle_user_status, name="toggle_user_status"),
    path("management/change-role/<int:user_id>/", views.change_user_role, name="change_user_role"),
    path("management/reset-password/<int:user_id>/", views.admin_reset_password, name="admin_reset_password"),
    path("management/force-logout/<int:user_id>/", views.force_logout, name="force_logout"),
]
