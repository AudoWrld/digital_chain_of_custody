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
from django.contrib.auth import get_user_model, login
from django.contrib.auth.tokens import default_token_generator
import pyotp
import qrcode
import io
import base64
import secrets
import json


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
            user.set_password(form.cleaned_data["password"])  # hash password
            user.save()

            current_site = get_current_site(request)
            subject = "verify your email"
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
                request, "Account created! Please check your email to verify."
            )
            return redirect("verification_sent")  # redirect after success
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

    if user and not user.is_active and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, "Your email has been verified successfully.")
        return redirect("second_authentication")
    else:
        return render(request, "accounts/link_expired.html", {"email": user.email if user else None})



def resend_verification_email(request):
    if request.method == "POST":
        email =  request.POST.get("email")
        try:
            user = User.objects.get(email=email)
            if user.is_active:
                messages.info(request, "this account is verified. please log in")
                return redirect('login')
            
            
            current_site = get_current_site(request)
            subject = "verify your email (Recent)"
            message = render_to_string( "emails/verification_email.html",
                {
                    "user": user,
                    "domain": current_site.domain,
                    "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                    "token": account_activation_token.make_token(user),
                },
            )
            send_mail(subject,message,settings.EMAIL_HOST_USER, [user.email],fail_silently=False)
            
            messages.success(
                request, "a new verification email has been sent. Please check your email."
            )
            return redirect("verification_sent")
        except User.DoesNotExist:
            messages.error(request, "No account found with this email.")
            return redirect("resend_verification")
    return render(request, "accounts/resend_verification.html")


@login_required
def second_authentication(request):
    user = request.user

    if not user.two_factor_enabled:
        print(f"2FA not enabled for user {user.email}, generating QR code")
        if request.method == "POST":
            token = request.POST.get("token")
            totp = pyotp.TOTP(user.two_factor_secret)
            if totp.verify(token):
                user.two_factor_enabled = True
                user.recovery_codes = generate_recovery_codes()
                user.save()
                messages.success(request, "Two-factor authentication setup complete!")
                return redirect("dashboard")
            else:
                messages.error(request, "Invalid token. Please try again.")
        else:
            if not user.two_factor_secret:
                user.two_factor_secret = pyotp.random_base32()
                user.save()
                print(f"Generated new secret: {user.two_factor_secret}")
            totp_uri = pyotp.totp.TOTP(user.two_factor_secret).provisioning_uri(
                name=user.email, issuer_name="YourAppName"
            )
            print(f"TOTP URI: {totp_uri}")
            img = qrcode.make(totp_uri)
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            qr_base64 = base64.b64encode(buffer.getvalue()).decode()
            print(f"QR base64 length: {len(qr_base64)}")
            return render(
                request,
                "accounts/second_auth.html",
                {
                    "qr_code": qr_base64,
                    "secret": user.two_factor_secret,
                    "show_recovery": True,
                },
            )
    # Subsequent logins → only ask for 2FA token
    else:
        if request.method == "POST":
            token = request.POST.get("token")
            recovery = request.POST.get("recovery_code")
            totp = pyotp.TOTP(user.two_factor_secret)

            if token and totp.verify(token):
                messages.success(request, "Two-factor authentication verified!")
                return redirect("dashboard")
            elif recovery:
                codes = json.loads(user.recovery_codes or "[]")
                if recovery in codes:
                    codes.remove(recovery)  # one-time use
                    user.recovery_codes = json.dumps(codes)
                    user.save()
                    messages.success(request, "Logged in using recovery code!")
                    return redirect("dashboard")
                else:
                    messages.error(request, "Invalid recovery code!")
            else:
                messages.error(request, "Invalid token or recovery code!")

        return render(request, "accounts/second_auth.html", {"qr_code": None})



def generate_recovery_codes():
    codes = [secrets.token_hex(4) for _ in range(8)]
    return json.dumps(codes)
