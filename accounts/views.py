from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Create your views here.


@login_required
def dashboard(request):
    return render(request, "accounts/dashboard.html")


def login(request):
    return render(request, "accounts/login.html")


def register(request):
    return render(request, "accounts/register.html")
