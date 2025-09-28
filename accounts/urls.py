from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login", views.login, name="login"),
    path("register", views.register, name="register"),
    path("verification-sent",views.verification_sent, name="verification_sent"),
    path("2fa",views.second_authentication, name="second_authentication"),
    path("verify/<uidb64>/<token>/", views.verify_email, name="verify_email")
]
