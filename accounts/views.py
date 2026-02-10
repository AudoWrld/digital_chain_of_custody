from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import User
from .forms import RegisterForm
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from .tokens import account_activation_token, password_reset_token
from django.utils.encoding import force_bytes, force_str
from django.conf import settings
from django.contrib.auth import (
    login as auth_login,
    get_user_model,
    authenticate,
    logout,
)
import pyotp
import qrcode
import io
import base64
import secrets
import json
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime


User = get_user_model()


def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False

            user.set_password(form.cleaned_data["password"])
            user.save()

            current_site = get_current_site(request)
            subject = "Verify your email"

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = account_activation_token.make_token(user)

            protocol = "https" if request.is_secure() else "http"

            message = render_to_string(
                "emails/verification_email.html",
                {
                    "user": user,
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
                [user.email],
                fail_silently=False,
            )

            messages.success(
                request, "Account created! Please check your email to verify."
            )

            request.session["pending_verification_email"] = user.email
            return redirect("verification_sent")

        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


def verification_sent(request):
    if request.user.is_authenticated and not request.user.verified:
        if not request.session.get("verification_email_sent"):
            current_site = get_current_site(request)
            subject = "Verify your email"

            uid = urlsafe_base64_encode(force_bytes(request.user.pk))
            token = account_activation_token.make_token(request.user)

            protocol = "https" if request.is_secure() else "http"

            message = render_to_string(
                "emails/verification_email.html",
                {
                    "user": request.user,
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
                [request.user.email],
                fail_silently=False,
            )
            request.session["verification_email_sent"] = True

    email = request.session.get("pending_verification_email")
    return render(request, "accounts/verification_sent.html", {"email": email})


def resend_verification_email(request):
    email = request.GET.get("email") or request.POST.get("email")

    if not email:
        messages.error(request, "Email is required.")
        return redirect("verification_sent")

    try:
        user = User.objects.get(email=email)
        if user.is_active:
            messages.info(request, "This account is already verified. Please log in.")
            return redirect("login")

        current_site = get_current_site(request)
        subject = "Verify your email (Recent)"
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = account_activation_token.make_token(user)
        protocol = "https" if request.is_secure() else "http"

        message = render_to_string(
            "emails/verification_email.html",
            {
                "user": user,
                "domain": current_site.domain,
                "protocol": protocol,
                "uid": uidb64,
                "token": token,
            },
        )

        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [user.email],
            fail_silently=False,
        )

        messages.success(request, f"A new verification email was sent to {user.email}.")
        return redirect(f"{reverse('verification_sent')}?email={user.email}")

    except User.DoesNotExist:
        messages.error(request, "No account found with this email.")
        return redirect("register")


def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and account_activation_token.check_token(user, token):
        user.is_active = True
        user.verified = True
        user.save()
        auth_login(request, user)
        messages.success(
            request, "Email verified successfully! Please proceed to complete 2FA."
        )
        return redirect("second_authentication")
    else:
        messages.error(request, "Verification link is invalid or has expired.")
        return redirect("register")


def generate_recovery_codes():
    codes = [secrets.token_hex(4).upper() for _ in range(10)]
    return json.dumps(codes)


@login_required
def second_authentication(request):
    user = request.user

    if not user.two_factor_enabled:
        if not user.two_factor_secret:
            user.two_factor_secret = pyotp.random_base32()
            user.save()

        totp = pyotp.TOTP(user.two_factor_secret)
        totp_uri = totp.provisioning_uri(name=user.email, issuer_name="ChainProof")

        img = qrcode.make(totp_uri)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        if request.method == "POST":
            token = request.POST.get("token")
            if totp.verify(token):
                user.two_factor_enabled = True
                user.recovery_codes = generate_recovery_codes()
                user.save()
                messages.success(
                    request, "2FA setup complete! Please save your recovery codes."
                )
                return redirect("recovery_codes_view")
            else:
                messages.error(request, "Invalid code. Please try again.")

        return render(
            request,
            "accounts/second_auth.html",
            {"qr_code": qr_base64, "secret": user.two_factor_secret},
        )

    else:
        if request.method == "POST":
            token = request.POST.get("token")
            totp = pyotp.TOTP(user.two_factor_secret)
            if totp.verify(token):
                messages.success(
                    request, "Two-factor authentication verified! Login successful."
                )
                if not request.user.recovery_codes_downloaded:
                    messages.info(
                        request,
                        "Please download your recovery codes before proceeding to your dashboard.",
                    )
                    return redirect("recovery_codes_view")

                if request.user.is_superuser:
                    return redirect("/admin/")
                elif request.user.role == "analyst":
                    return redirect("reports:dashboard")
                elif request.user.role == "custodian":
                    return redirect("custody:dashboard")
                elif request.user.role == "investigator":
                    return redirect("cases:case_list")
                else:
                    return redirect("dashboard:dashboard")
            else:
                messages.error(request, "Invalid code. Please try again.")

        return render(request, "accounts/second_auth.html")


@login_required
def recovery_codes_view(request):
    user = request.user
    if not user.recovery_codes:
        messages.error(request, "No recovery codes found.")
        return redirect("dashboard:dashboard")

    codes = json.loads(user.recovery_codes)
    return render(request, "accounts/recovery_codes.html", {"codes": codes})


@login_required
def verify_recovery_code(request):
    user = request.user
    if not user.two_factor_enabled:
        messages.error(
            request, "Two-factor authentication is not enabled for your account."
        )
        return redirect("second_authentication")

    if request.method == "POST":
        code = request.POST.get("recovery_code").strip().upper()

        try:
            recovery_codes = json.loads(user.recovery_codes or "[]")
        except json.JSONDecodeError:
            recovery_codes = []

        if code in recovery_codes:
            recovery_codes.remove(code)
            user.recovery_codes = json.dumps(recovery_codes)
            user.save()

            messages.success(request, "Recovery code verified! Please set up new 2FA.")
            return redirect("setup_new_2fa")
        else:
            messages.error(request, "Invalid recovery code. Please try again.")

    return render(request, "accounts/verify_recovery_code.html")


def proceed_to_dashboard(request):
    return render(request, "accounts/proceed_to_dashboard.html")


def setup_new_2fa(request):
    user = request.user
    user.two_factor_enabled = False
    user.recovery_codes_downloaded = False
    user.recovery_codes = ""
    user.save()
    return redirect("second_authentication")


@login_required
def download_recovery_codes(request):
    user = request.user

    if not user.recovery_codes:
        messages.error(request, "No recovery codes found.")
        return redirect("dashboard:dashboard")

    codes = json.loads(user.recovery_codes)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    p.setFillColorRGB(0.2, 0.3, 0.5)
    p.rect(0, height - 100, width, 100, fill=True, stroke=False)
    p.setFillColorRGB(1, 1, 1)
    p.setFont("Helvetica-Bold", 24)
    p.drawCentredString(width / 2, height - 50, "ChainProof")
    p.setFont("Helvetica", 14)
    p.drawCentredString(width / 2, height - 75, "Account Recovery Codes")

    p.setFillColorRGB(1, 0.95, 0.8)
    p.rect(72, height - 200, width - 144, 80, fill=True, stroke=True)
    p.setFillColorRGB(0, 0, 0)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(90, height - 140, "Important Security Information")

    p.setFont("Helvetica", 11)
    p.drawString(
        90, height - 160, "• Store these codes securely (safe or password manager)."
    )
    p.drawString(90, height - 177, "• Each code can only be used once.")
    p.drawString(
        90, height - 194, "• Use these if you lose access to your authenticator app."
    )

    p.setFont("Helvetica-Bold", 14)
    p.drawString(72, height - 230, "Your Recovery Codes:")

    p.setFont("Courier-Bold", 12)
    y = height - 260
    x_col1 = 90
    x_col2 = width / 2 + 20

    for i, code in enumerate(codes):
        if i < 5:
            p.drawString(x_col1, y, f"{i+1}. {code}")
            y -= 25
        else:
            if i == 5:
                y = height - 260
            p.drawString(x_col2, y, f"{i+1}. {code}")
            y -= 25

    p.setFont("Helvetica-Oblique", 9)
    p.setFillColorRGB(0.5, 0.5, 0.5)
    p.drawCentredString(
        width / 2,
        50,
        f"Generated for {user.username} on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
    )
    p.drawCentredString(width / 2, 35, "ChainProof - Secure Authentication")

    p.showPage()
    p.save()

    buffer.seek(0)
    user.recovery_codes_downloaded = True
    user.save()
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = (
        'attachment; filename="chainproof_recovery_codes.pdf"'
    )
    messages.success(
        request,
        "Recovery codes downloaded successfully. You can now proceed to your dashboard.",
    )

    return response


def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "No account found with that email.")
            return redirect("forgot_password")

        current_site = get_current_site(request)
        subject = "Reset your password"
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = password_reset_token.make_token(user)
        protocol = "https" if request.is_secure() else "http"

        message = render_to_string(
            "emails/reset_password_email.html",
            {
                "user": user,
                "domain": current_site.domain,
                "protocol": protocol,
                "uid": uidb64,
                "token": token,
            },
        )

        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [user.email],
            fail_silently=False,
        )

        messages.success(request, "Password reset email sent. Check your inbox.")
        return redirect("login")

    return render(request, "accounts/forgot_password.html")


def reset_password(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and password_reset_token.check_token(user, token):
        if request.method == "POST":
            new_password = request.POST.get("password")
            confirm_password = request.POST.get("confirm_password")

            if new_password != confirm_password:
                messages.error(request, "Passwords do not match.")
                return redirect(request.path)

            user.set_password(new_password)
            user.save()
            messages.success(request, "Password reset successful. You can now log in.")
            return redirect("login")

        return render(request, "accounts/reset_password.html", {"validlink": True})
    else:
        messages.error(request, "This reset link is invalid or has expired.")
        return render(request, "accounts/reset_password.html", {"validlink": False})


def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "No account found with this email.")
            return redirect("login")
        if not user.verified:
            if not request.session.get("verification_email_sent"):
                current_site = get_current_site(request)
                subject = "Verify your email"

                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = account_activation_token.make_token(user)

                protocol = "https" if request.is_secure() else "http"

                message = render_to_string(
                    "emails/verification_email.html",
                    {
                        "user": user,
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
                    [user.email],
                    fail_silently=False,
                )
                request.session["verification_email_sent"] = True

            request.session["pending_verification_email"] = user.email
            messages.warning(
                request,
                "Your account isn't verified yet. Please check your email or resend the verification link.",
            )
            return redirect("verification_sent")
        user = authenticate(request, email=email, password=password)
        if user is not None:
            auth_login(request, user)
            if not user.two_factor_enabled:
                messages.info(
                    request, "You must enable two-factor authentication to continue."
                )
                return redirect("second_authentication")

            return redirect("second_authentication")

        else:
            messages.error(request, "Invalid email or password.")
            return redirect("login")

    return render(request, "accounts/login.html")


def logout_view(request):
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, "You've been logged out successfully.")
    else:
        messages.info(request, "You're not logged in.")
    return redirect("homepage")


@login_required
def user_management(request):
    if not request.user.is_superuser and request.user.role != "admin":
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Only administrators can access user management.")

    from django.db.models import Count, Q
    from cases.models import Case
    from custody.models import CaseStorage

    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    inactive_users = total_users - active_users

    users_by_role = {}
    for role, role_name in User.ROLE:
        count = User.objects.filter(role=role).count()
        if count > 0:
            users_by_role[role] = {"name": role_name, "count": count}

    alerts = []

    custodians = User.objects.filter(role="custodian")
    overloaded_custodians = []
    for custodian in custodians:
        storage_count = CaseStorage.objects.filter(custodian=custodian).count()
        if storage_count > 5:
            overloaded_custodians.append({"user": custodian, "count": storage_count})
    if overloaded_custodians:
        alerts.append(
            {
                "type": "warning",
                "title": "Custodians Overloaded",
                "message": f"{len(overloaded_custodians)} custodians have more than 5 active storages",
                "details": overloaded_custodians,
            }
        )

    users_without_roles = User.objects.filter(role="").count()
    if users_without_roles > 0:
        alerts.append(
            {
                "type": "error",
                "title": "Users Without Roles",
                "message": f"{users_without_roles} users have no role assigned",
            }
        )

    disabled_with_cases = []
    disabled_users = User.objects.filter(is_active=False)
    for user in disabled_users:
        cases_count = Case.objects.filter(created_by=user, case_status="Open").count()
        if cases_count > 0:
            disabled_with_cases.append({"user": user, "count": cases_count})
    if disabled_with_cases:
        alerts.append(
            {
                "type": "error",
                "title": "Disabled Accounts With Active Cases",
                "message": f"{len(disabled_with_cases)} disabled users have open cases",
                "details": disabled_with_cases,
            }
        )

    from django.utils import timezone
    from datetime import timedelta

    recent_users = User.objects.filter(
        date_joined__gte=timezone.now() - timedelta(days=7)
    ).count()

    never_logged_in = User.objects.filter(last_login__isnull=True).count()

    return render(
        request,
        "accounts/user_management.html",
        {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": inactive_users,
            "users_by_role": users_by_role,
            "alerts": alerts,
            "recent_users": recent_users,
            "never_logged_in": never_logged_in,
            "overloaded_custodians": overloaded_custodians,
            "disabled_with_cases": disabled_with_cases,
        },
    )


@login_required
def user_list(request):
    if not request.user.is_superuser and request.user.role != "admin":
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Only administrators can access user management.")

    from django.db.models import Q
    from cases.models import Case
    from custody.models import CaseStorage

    users = User.objects.all().select_related()

    search_query = request.GET.get("search", "")
    if search_query:
        users = users.filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(username__icontains=search_query)
        )

    role_filter = request.GET.get("role", "")
    if role_filter:
        users = users.filter(role=role_filter)

    status_filter = request.GET.get("status", "")
    if status_filter == "active":
        users = users.filter(is_active=True)
    elif status_filter == "inactive":
        users = users.filter(is_active=False)

    sort_by = request.GET.get("sort", "name")
    sort_order = request.GET.get("order", "asc")

    if sort_by == "name":
        users = users.order_by("first_name" if sort_order == "asc" else "-first_name")
    elif sort_by == "email":
        users = users.order_by("email" if sort_order == "asc" else "-email")
    elif sort_by == "role":
        users = users.order_by("role" if sort_order == "asc" else "-role")
    elif sort_by == "status":
        users = users.order_by("is_active" if sort_order == "asc" else "-is_active")
    elif sort_by == "last_login":
        users = users.order_by("last_login" if sort_order == "asc" else "-last_login")

    users_with_workload = []
    for user in users:
        if user.role in ["analyst", "investigator"]:
            workload = (
                Case.objects.filter(Q(created_by=user) | Q(assigned_investigators=user))
                .distinct()
                .count()
            )
        elif user.role == "custodian":
            workload = CaseStorage.objects.filter(custodian=user).count()
        else:
            workload = Case.objects.filter(created_by=user).count()

        users_with_workload.append({"user": user, "workload": workload})

    return render(
        request,
        "accounts/user_list.html",
        {
            "users": users_with_workload,
            "search_query": search_query,
            "role_filter": role_filter,
            "status_filter": status_filter,
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
    )


@login_required
def user_detail(request, user_id):
    if not request.user.is_superuser and request.user.role != "admin":
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Only administrators can access user management.")

    from django.db.models import Q
    from cases.models import Case, CaseAuditLog
    from custody.models import CaseStorage
    from evidence.models import Evidence

    target_user = get_object_or_404(User, id=user_id)

    basic_info = {
        "full_name": target_user.get_full_name(),
        "email": target_user.email,
        "username": target_user.username,
        "date_joined": target_user.date_joined,
        "last_login": target_user.last_login,
        "role": target_user.get_role_display(),
    }

    assignments = {}
    if target_user.role in ["analyst", "investigator"]:
        cases_created = Case.objects.filter(created_by=target_user)
        cases_assigned = Case.objects.filter(assigned_investigators=target_user)

        assignments["cases_created"] = cases_created.count()
        assignments["cases_assigned"] = cases_assigned.count()
        assignments["total_cases"] = cases_created.union(cases_assigned).count()
        assignments["cases_list"] = list(
            cases_created.union(cases_assigned).distinct()[:10]
        )

    elif target_user.role == "custodian":
        storages = CaseStorage.objects.filter(custodian=target_user)
        assignments["storages_count"] = storages.count()
        assignments["storages_list"] = list(storages[:10])

    elif target_user.role == "regular_user":
        cases_created = Case.objects.filter(created_by=target_user)
        assignments["cases_created"] = cases_created.count()
        assignments["cases_list"] = list(cases_created[:10])

    security_info = {
        "is_active": target_user.is_active,
        "is_superuser": target_user.is_superuser,
        "two_factor_enabled": target_user.two_factor_enabled,
        "verified": target_user.verified,
        "last_password_change": getattr(target_user, "last_password_change", None),
        "failed_logins": getattr(target_user, "failed_login_attempts", 0),
    }

    recent_activity = CaseAuditLog.objects.filter(user=target_user).order_by(
        "-timestamp"
    )[:10]

    return render(
        request,
        "accounts/user_detail.html",
        {
            "target_user": target_user,
            "basic_info": basic_info,
            "assignments": assignments,
            "security_info": security_info,
            "recent_activity": recent_activity,
        },
    )


@login_required
def toggle_user_status(request, user_id):
    if not request.user.is_superuser and request.user.role != "admin":
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Only administrators can perform this action.")

    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("accounts:user_list")

    target_user = get_object_or_404(User, id=user_id)

    if target_user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("accounts:user_detail", user_id=user_id)

    if target_user.is_superuser:
        messages.error(request, "Cannot deactivate superuser accounts.")
        return redirect("accounts:user_detail", user_id=user_id)

    new_status = not target_user.is_active
    action = "activated" if new_status else "deactivated"

    target_user.is_active = new_status
    target_user.save()

    from cases.models import CaseAuditLog

    CaseAuditLog.log_action(
        user=request.user,
        action=f"User {action}",
        details=f"User {target_user.get_full_name()} ({target_user.email}) was {action} by {request.user.get_full_name()}",
    )

    messages.success(request, f"User {target_user.get_full_name()} has been {action}.")
    return redirect("accounts:user_detail", user_id=user_id)


@login_required
def change_user_role(request, user_id):
    if not request.user.is_superuser and request.user.role != "admin":
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Only administrators can perform this action.")

    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("accounts:user_list")

    target_user = get_object_or_404(User, id=user_id)
    new_role = request.POST.get("role")

    if new_role not in dict(User.ROLE):
        messages.error(request, "Invalid role selected.")
        return redirect("accounts:user_detail", user_id=user_id)

    old_role = target_user.role
    target_user.role = new_role
    target_user.save()

    from cases.models import CaseAuditLog

    CaseAuditLog.log_action(
        user=request.user,
        action="User role changed",
        details=f"User {target_user.get_full_name()} ({target_user.email}) role changed from {old_role} to {new_role} by {request.user.get_full_name()}",
    )

    messages.success(request, f"User role changed from {old_role} to {new_role}.")
    return redirect("accounts:user_detail", user_id=user_id)


@login_required
def admin_reset_password(request, user_id):
    if not request.user.is_superuser and request.user.role != "admin":
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Only administrators can perform this action.")

    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("accounts:user_list")

    target_user = get_object_or_404(User, id=user_id)

    import secrets

    temp_password = secrets.token_urlsafe(12)

    target_user.set_password(temp_password)
    target_user.save()

    from cases.models import CaseAuditLog

    CaseAuditLog.log_action(
        user=request.user,
        action="Password reset by admin",
        details=f"Password reset for user {target_user.get_full_name()} ({target_user.email}) by {request.user.get_full_name()}",
    )

    messages.success(
        request,
        f"Password reset for {target_user.get_full_name()}. Temporary password: {temp_password}",
    )
    return redirect("accounts:user_detail", user_id=user_id)


@login_required
def force_logout(request, user_id):
    if not request.user.is_superuser and request.user.role != "admin":
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Only administrators can perform this action.")

    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("accounts:user_list")

    target_user = get_object_or_404(User, id=user_id)

    if target_user == request.user:
        messages.error(request, "You cannot force logout your own account.")
        return redirect("accounts:user_detail", user_id=user_id)

    from cases.models import CaseAuditLog

    CaseAuditLog.log_action(
        user=request.user,
        action="Force logout",
        details=f"User {target_user.get_full_name()} ({target_user.email}) was forced to logout by {request.user.get_full_name()}",
    )

    messages.success(
        request, f"User {target_user.get_full_name()} has been forced to logout."
    )
    return redirect("accounts:user_detail", user_id=user_id)
