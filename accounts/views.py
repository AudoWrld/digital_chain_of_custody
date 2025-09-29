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


@login_required
def dashboard(request):
    return render(request, "accounts/dashboard.html")


def login(request):
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
        messages.success(
            request, "Email verified successfully! Please proceed to complete 2FA."
        )
        return redirect("second_authentication")
    else:
        messages.error(request, "Verification link is invalid or has expired.")
        return redirect("register")


def second_authentication(request):
    return render(request, "accounts/second_auth.html")
