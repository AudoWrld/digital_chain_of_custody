from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import User
from .forms import RegisterForm
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from .tokens import account_activation_token
from django.utils.encoding import force_bytes, force_str
from django.urls import reverse
from django.conf import settings
from django.contrib.auth import login as auth_login, get_user_model
from django.contrib.auth.tokens import default_token_generator
import pyotp
import qrcode
import io
import base64
import secrets
import json
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

User = get_user_model()


@login_required
def dashboard(request):
    return render(request, "accounts/dashboard.html")


def login_view(request):
    return render(request, "accounts/login.html")


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

            return redirect("verification_sent")

        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


def verification_sent(request):
    return render(request, "accounts/verification_sent.html")


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


def resend_verification_email(request):
    if request.method == "POST":
        email = request.POST.get("email")
        try:
            user = User.objects.get(email=email)
            if user.is_active:
                messages.info(request, "this account is verified. please log in")
                return redirect("login")

            current_site = get_current_site(request)
            subject = "verify your email (Recent)"
            message = render_to_string(
                "emails/verification_email.html",
                {
                    "user": user,
                    "domain": current_site.domain,
                    "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                    "token": account_activation_token.make_token(user),
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
                request,
                "a new verification email has been sent. Please check your email.",
            )
            return redirect("verification_sent")
        except User.DoesNotExist:
            messages.error(request, "No account found with this email.")
            return redirect("resend_verification")
    return render(request, "accounts/resend_verification.html")


# Generate Codes
def generate_recovery_codes():
    codes = [secrets.token_hex(4).upper() for _ in range(5)]
    return json.dumps(codes)


@login_required
def second_authentication(request):
    user = request.user

    # Step 1: if 2FA not yet enabled, show QR and handle setup
    if not user.two_factor_enabled:
        if not user.two_factor_secret:
            # Generate new secret if user doesn't have one
            user.two_factor_secret = pyotp.random_base32()
            user.save()

        totp = pyotp.TOTP(user.two_factor_secret)
        totp_uri = totp.provisioning_uri(name=user.email, issuer_name="ChainProof")

        # Generate QR code
        img = qrcode.make(totp_uri)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        if request.method == "POST":
            token = request.POST.get("token")
            if totp.verify(token):
                user.two_factor_enabled = True
                user.save()
                user.recovery_codes = generate_recovery_codes()
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

    # Step 2: If 2FA already enabled, verify token during login
    else:
        if request.method == "POST":
            token = request.POST.get("token")
            totp = pyotp.TOTP(user.two_factor_secret)
            if totp.verify(token):
                messages.success(request, "Two-factor authentication verified!")
                return redirect("dashboard")
            else:
                messages.error(request, "Invalid code. Please try again.")

        return render(request, "accounts/second_auth.html")


@login_required
def recovery_codes_view(request):
    user = request.user
    if not user.recovery_codes:
        messages.error(request, "No recovery codes found.")
        return redirect("dashboard")

    codes = json.loads(user.recovery_codes)
    return render(request, "accounts/recovery_codes.html", {"codes": codes})


@login_required
def download_recovery_codes(request):
    user = request.user

    # Make sure the user has recovery codes
    if not user.recovery_codes:
        messages.error(request, "No recovery codes found.")
        return redirect("dashboard")

    codes = json.loads(user.recovery_codes)

    # Create a PDF in memory
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    p.setFont("Helvetica-Bold", 16)
    p.drawString(72, height - 72, "Your Recovery Codes")

    p.setFont("Helvetica", 12)
    p.drawString(72, height - 100, "Keep these codes in a safe place.")
    p.drawString(
        72,
        height - 120,
        "Each can be used once if you lose access to your authenticator app.",
    )
    y = height - 160

    for code in codes:
        p.drawString(100, y, f"• {code}")
        y -= 20

    p.showPage()
    p.save()

    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="recovery_codes.pdf"'
    return response
