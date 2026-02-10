from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
    AbstractUser,
)
from django.db import models


class UserProfileManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, first_name, last_name, password=None, **extra_fields):
        extra_fields.setdefault("is_active", False)
        extra_fields.setdefault("role", "regular_user")
        if not email:
            raise ValueError("The Email must be set")
        email = self.normalize_email(email)
        username = email.split("@")[0]
        user = self.model(
            email=email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, email, first_name, last_name, password=None, **extra_fields
    ):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", "superuser")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, first_name, last_name, password, **extra_fields)


class User(AbstractUser, PermissionsMixin):
    ROLE = [
        ("regular_user", "Regular User"),
        ("investigator", "Investigator"),
        ("analyst", "Analyst"),
        ("custodian", "Custodian"),
        ("auditor", "Auditor"),
    ]
    first_name = models.CharField(null=False, max_length=15, blank=False)
    last_name = models.CharField(null=False, max_length=15, blank=False)
    username = models.CharField(max_length=150, unique=False, blank=True, null=True)
    email = models.EmailField(null=False, unique=True, blank=False)
    verified = models.BooleanField(default=False, blank=True, null=True)
    role = models.CharField(
        max_length=20,
        choices=ROLE,
        default="investigator",
    )
    profile_picture = models.ImageField(
        upload_to="profile_pics/", blank=True, null=True
    )
    two_factor_secret = models.CharField(max_length=16, blank=True, null=True)
    two_factor_enabled = models.BooleanField(default=False)
    recovery_codes = models.TextField(blank=True, null=True)
    recovery_codes_downloaded = models.BooleanField(default=False, blank=True, null=True)
    failed_login_attempts = models.IntegerField(default=0)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    
    groups = models.ManyToManyField(
        "auth.Group",
        related_name="custom_user_groups",
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="custom_user_permissions",
        blank=True,
    )
    objects = UserProfileManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]
    
 


    def __str__(self):
        return f"{self.first_name} {self.last_name}"
