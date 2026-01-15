from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="homepage"),
    path("terms-and-condition/", views.terms, name="terms"),
    path("privacy-policy/", views.privacy, name="privacy"),
    path("contact/", views.contact, name="contact"),
]
