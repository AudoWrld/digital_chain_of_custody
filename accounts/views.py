from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import User
from .forms import RegisterForm


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
            user.set_password(form.cleaned_data["password"])  # hash password
            user.save()
            messages.success(request, "Account created successfully!")
            return redirect("dashboard")  # redirect after success
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})
