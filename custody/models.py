from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.utils import timezone
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
import base64
import os


class CaseStorage(models.Model):
    case = models.OneToOneField(
        "cases.Case", on_delete=models.CASCADE, related_name="storage"
    )
    storage_name = models.CharField(max_length=200, unique=True)
    storage_path = models.CharField(max_length=500)
    encryption_key = models.BinaryField(editable=False, null=True)
    encryption_iv = models.BinaryField(editable=False, null=True)
    is_locked = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Case Storage"
        verbose_name_plural = "Case Storages"

    def __str__(self):
        return f'{self.storage_name} - {"Locked" if self.is_locked else "Unlocked"}'

    def save(self, *args, **kwargs):
        if not self.encryption_key:
            self.encryption_key = os.urandom(32)
            self.encryption_iv = os.urandom(16)
        super().save(*args, **kwargs)

    def get_cipher(self):
        cipher = Cipher(
            algorithms.AES(self.encryption_key),
            modes.CBC(self.encryption_iv),
            backend=default_backend(),
        )
        return cipher

    def _pad_data(self, data):
        data = data.encode("utf-8")
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()
        return padded_data

    def _unpad_data(self, padded_data):
        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()
        return data

    def encrypt_data(self, data):
        cipher = self.get_cipher()
        encryptor = cipher.encryptor()
        padded_data = self._pad_data(data)
        encrypted_bytes = encryptor.update(padded_data) + encryptor.finalize()
        return base64.b64encode(encrypted_bytes).decode()

    def decrypt_data(self, encrypted_data):
        cipher = self.get_cipher()
        decryptor = cipher.decryptor()
        encrypted_bytes = base64.b64decode(encrypted_data)
        padded_data = decryptor.update(encrypted_bytes) + decryptor.finalize()
        data = self._unpad_data(padded_data)
        return data.decode("utf-8")

    @property
    def evidence_count(self):
        return EvidenceStorage.objects.filter(
            storage_location__case_storage=self
        ).count()

    @property
    def is_empty(self):
        return self.evidence_count == 0

    @property
    def current_custodian(self):
        assignment = self.custodian_assignments.filter(is_active=True).first()
        return assignment.custodian if assignment else None

    def can_unlock(self, user):
        if not self.is_active:
            return False
        if user.is_superuser:
            return True
        if user == self.current_custodian:
            return True
        if user in self.case.assigned_investigators.all():
            return True
        if user == self.case.created_by:
            return True
        return False

    def unlock(self, user):
        if not self.can_unlock(user):
            raise PermissionError(
                "User does not have permission to unlock this storage"
            )
        self.is_locked = False
        self.save()
        StorageLog.log_action(self, user, "unlock", "Storage unlocked for operations")

    def lock(self, user):
        self.is_locked = True
        self.save()
        StorageLog.log_action(
            self, user, "lock", "Storage locked to prevent modifications"
        )

    def can_upload(self, user):
        if not self.is_active:
            return False
        if self.is_locked:
            return False
        if user.is_superuser:
            return True
        if user == self.current_custodian:
            return True
        if user in self.case.assigned_investigators.all():
            return True
        if user == self.case.created_by:
            return True
        return False


class CustodianAssignment(models.Model):
    case_storage = models.ForeignKey(
        CaseStorage, on_delete=models.CASCADE, related_name="custodian_assignments"
    )
    custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="custodian_assignments",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custodian_assignments_made",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custodian_assignments_deactivated",
    )
    deactivation_reason = models.TextField(blank=True)
    assignment_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-assigned_at"]
        verbose_name = "Custodian Assignment"
        verbose_name_plural = "Custodian Assignments"

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.custodian} - {self.case_storage.storage_name} ({status})"

    def deactivate(self, user, reason=""):
        self.is_active = False
        self.deactivated_at = timezone.now()
        self.deactivated_by = user
        self.deactivation_reason = reason
        self.save()
        StorageLog.log_action(
            self.case_storage,
            user,
            "custodian_change",
            f"Custodian {self.custodian} deactivated. Reason: {reason}",
        )


class CustodyTransfer(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("completed", "Completed"),
    ]

    evidence = models.ForeignKey(
        "evidence.Evidence", on_delete=models.CASCADE, related_name="custody_transfers"
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="custody_transfers_from",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="custody_transfers_to",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="custody_transfer_requests",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    reason = models.TextField()
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_custody_transfers",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Custody Transfer: {self.evidence.description} from {self.from_user} to {self.to_user}"


class StorageLocation(models.Model):
    LOCATION_TYPE_CHOICES = [
        ("physical", "Physical Storage"),
        ("digital", "Digital Storage"),
        ("cloud", "Cloud Storage"),
    ]

    name = models.CharField(max_length=200)
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPE_CHOICES)
    capacity = models.BigIntegerField(
        help_text="Capacity in bytes", null=True, blank=True
    )
    used_space = models.BigIntegerField(default=0, help_text="Used space in bytes")
    is_active = models.BooleanField(default=True)
    managed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="managed_storage_locations",
    )
    case_storage = models.ForeignKey(
        CaseStorage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="storage_locations",
        help_text="Link to case-specific storage",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def available_space(self):
        if self.capacity:
            return self.capacity - self.used_space
        return None

    @property
    def usage_percentage(self):
        if self.capacity and self.capacity > 0:
            return (self.used_space / self.capacity) * 100
        return None


class EvidenceStorage(models.Model):
    evidence = models.OneToOneField(
        "evidence.Evidence", on_delete=models.CASCADE, related_name="storage"
    )
    storage_location = models.ForeignKey(
        StorageLocation, on_delete=models.CASCADE, related_name="evidence_items"
    )
    stored_at = models.DateTimeField(auto_now_add=True)
    last_accessed = models.DateTimeField(auto_now=True)
    access_count = models.IntegerField(default=0)
    is_immutable = models.BooleanField(default=True, editable=False)

    class Meta:
        ordering = ["-stored_at"]

    def __str__(self):
        return f"Storage: {self.evidence.description} at {self.storage_location.name}"

    def delete(self, *args, **kwargs):
        if self.evidence.is_immutable:
            raise ValidationError(
                "Original evidence cannot be deleted. It is immutable."
            )
        return super().delete(*args, **kwargs)

    def record_access(self, user):
        self.last_accessed = timezone.now()
        self.access_count += 1
        self.save()
        StorageLog.log_action(
            self.storage_location.case_storage,
            user,
            "access",
            f"Accessed evidence {self.evidence.id}",
        )


class CustodyLog(models.Model):
    ACTION_CHOICES = [
        ("stored", "Stored"),
        ("retrieved", "Retrieved"),
        ("transferred", "Transferred"),
        ("verified", "Verified"),
        ("archived", "Archived"),
        ("viewed", "Viewed"),
        ("downloaded", "Downloaded"),
        ("moved", "Moved"),
    ]

    evidence = models.ForeignKey(
        "evidence.Evidence", on_delete=models.CASCADE, related_name="custody_logs"
    )
    case = models.ForeignKey(
        "cases.Case", on_delete=models.CASCADE, related_name="custody_logs"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="custody_logs",
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    details = models.TextField(blank=True)
    from_location = models.ForeignKey(
        StorageLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custody_logs_from",
    )
    to_location = models.ForeignKey(
        StorageLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custody_logs_to",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custody_logs_received",
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action}: {self.evidence.description} by {self.user}"

    @classmethod
    def log_action(
        cls,
        evidence,
        case,
        user,
        action,
        details="",
        from_location=None,
        to_location=None,
        to_user=None,
    ):
        return cls.objects.create(
            evidence=evidence,
            case=case,
            user=user,
            action=action,
            details=details,
            from_location=from_location,
            to_location=to_location,
            to_user=to_user,
        )


class StorageLog(models.Model):
    ACTION_CHOICES = [
        ("created", "Storage Created"),
        ("upload", "Evidence Uploaded"),
        ("access", "Evidence Accessed"),
        ("lock", "Storage Locked"),
        ("unlock", "Storage Unlocked"),
        ("custodian_change", "Custodian Changed"),
        ("transfer", "Custody Transferred"),
        ("delete_attempt", "Delete Attempt"),
    ]

    storage = models.ForeignKey(
        CaseStorage, on_delete=models.CASCADE, related_name="storage_logs"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="storage_logs",
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    details = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"[{self.timestamp}] {self.action} on {self.storage.storage_name}"

    @classmethod
    def log_action(cls, storage, user, action, details="", ip_address=None):
        return cls.objects.create(
            storage=storage,
            user=user,
            action=action,
            details=details,
            ip_address=ip_address,
        )


def get_least_loaded_custodian():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    custodians = User.objects.filter(role="custodian", is_active=True)
    if not custodians.exists():
        return None

    custodian_loads = []
    for custodian in custodians:
        active_assignments = CustodianAssignment.objects.filter(
            custodian=custodian, is_active=True
        ).count()
        custodian_loads.append((custodian, active_assignments))

    custodian_loads.sort(key=lambda x: x[1])
    return custodian_loads[0][0] if custodian_loads else None


@receiver(post_save, sender="cases.Case")
def create_case_storage(sender, instance, created, **kwargs):
    if created:
        storage_name = f"STORAGE_{instance.case_id}"
        storage_path = f"/secure/storage/{instance.case_id}"

        case_storage = CaseStorage.objects.create(
            case=instance,
            storage_name=storage_name,
            storage_path=storage_path,
            is_locked=True,
            is_active=True,
        )

        storage_location = StorageLocation.objects.create(
            name=f"{storage_name}_PRIMARY",
            location_type="digital",
            case_storage=case_storage,
            is_active=True,
        )

        StorageLog.log_action(
            case_storage,
            None,
            "created",
            f"Storage created for case {instance.case_id}",
        )

        custodian = get_least_loaded_custodian()
        if custodian:
            CustodianAssignment.objects.create(
                case_storage=case_storage,
                custodian=custodian,
                assigned_by=None,
                is_active=True,
                assignment_reason="System-assigned based on least-loaded custodian rule",
            )
            StorageLog.log_action(
                case_storage,
                None,
                "custodian_change",
                f"Custodian {custodian.username} assigned by system",
            )
