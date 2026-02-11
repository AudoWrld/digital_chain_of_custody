from django.db import models
from django.conf import settings
from django.utils import timezone
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
from django.core.files.base import ContentFile
from django.core.exceptions import ObjectDoesNotExist
import base64
import os
import hashlib
from datetime import datetime


class EncryptionKey(models.Model):
    case = models.OneToOneField(
        "Case", on_delete=models.CASCADE, related_name="encryption_key", unique=True
    )
    key = models.BinaryField(editable=False)
    iv = models.BinaryField(null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = os.urandom(32)
            self.iv = os.urandom(16)
        super().save(*args, **kwargs)

    def get_cipher(self):
        cipher = Cipher(
            algorithms.AES(self.key), modes.CBC(self.iv), backend=default_backend()
        )
        return cipher

    def __str__(self):
        return f"AES-256 encryption key for Case ID: {self.case.case_id}"


class Case(models.Model):
    STATUS_CHOICES = [
        ("Open", "Open"),
        ("Pending Admin Approval", "Pending Admin Approval"),
        ("Approved & Assigned", "Approved & Assigned"),
        ("Under Review", "Under Review"),
        ("Closed", "Closed"),
        ("Archived", "Archived"),
        ("Invalid", "Invalid"),
        ("Withdrawn", "Withdrawn"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    CASE_CATEGORIES = [
        ("Homicide", "Homicide"),
        ("Assault and Violence", "Assault and Violence"),
        ("Sexual Offenses", "Sexual Offenses"),
        ("Theft and Property Crimes", "Theft and Property Crimes"),
        ("Fraud and Financial Crimes", "Fraud and Financial Crimes"),
        ("Drug Offenses", "Drug Offenses"),
        ("Cybercrime", "Cybercrime"),
        ("Domestic and Family Violence", "Domestic and Family Violence"),
        ("Human Trafficking", "Human Trafficking"),
        ("Child Abuse and Exploitation", "Child Abuse and Exploitation"),
        ("Elder Abuse", "Elder Abuse"),
        ("Public Order and Nuisance", "Public Order and Nuisance"),
        ("Traffic and Vehicle Offenses", "Traffic and Vehicle Offenses"),
        ("White Collar and Corporate Crime", "White Collar and Corporate Crime"),
        ("Terrorism and National Security", "Terrorism and National Security"),
    ]

    case_id = models.CharField(max_length=20, unique=True, editable=False, null=True, blank=True)
    case_title = models.TextField()
    case_description = models.TextField()
    case_category = models.CharField(max_length=50, choices=CASE_CATEGORIES)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cases"
    )
    case_status = models.CharField(
        max_length=200, choices=STATUS_CHOICES, default="Open"
    )
    case_status_notes = models.TextField()
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    invalid_reason = models.TextField(blank=True, null=True)
    withdraw_reason = models.TextField(blank=True, null=True)
    close_reason = models.TextField(blank=True, null=True)
    closure_approved = models.BooleanField(default=False)
    closure_creator_approved = models.BooleanField(default=False)
    case_priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="medium"
    )
    assigned_investigators = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="assigned_cases", blank=True
    )
    closure_requested = models.BooleanField(default=False)
    final_report = models.TextField(blank=True, null=True)
    conclusion = models.TextField(blank=True, null=True)
    case_concluded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="concluded_cases"
    )
    case_concluded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        title_preview = (
            self.case_title[:30] + "..."
            if self.case_title and len(self.case_title) > 30
            else self.case_title
        )
        return f"{self.case_id} - {title_preview or 'N/A'} - {self.case_status}"

    def generate_case_id(self):
        now = timezone.now()
        date_str = now.strftime("%Y%m%d")
        year_count = Case.objects.filter(date_created__year=now.year).count()
        return f"CASE{date_str}{year_count + 1:04d}"

    def _pad_data(self, data):
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()
        return padded_data

    def _unpad_data(self, padded_data):
        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()
        return data

    def encrypt_field(self, value):
        if value is None or value == "":
            return None
        cipher = self.encryption_key.get_cipher()
        encryptor = cipher.encryptor()

        data = value.encode("utf-8")
        padded_data = self._pad_data(data)
        encrypted_bytes = encryptor.update(padded_data) + encryptor.finalize()

        return base64.b64encode(encrypted_bytes).decode()

    def encrypt_field_with_cipher(self, value, cipher):
        if value is None or value == "":
            return None
        encryptor = cipher.encryptor()

        data = value.encode("utf-8")
        padded_data = self._pad_data(data)
        encrypted_bytes = encryptor.update(padded_data) + encryptor.finalize()

        return base64.b64encode(encrypted_bytes).decode()

    def decrypt_field(self, encrypted_value):
        if not encrypted_value:
            return ""
        try:
            cipher = self.encryption_key.get_cipher()
            decryptor = cipher.decryptor()

            encrypted_bytes = base64.b64decode(encrypted_value)
            padded_data = decryptor.update(encrypted_bytes) + decryptor.finalize()
            data = self._unpad_data(padded_data)

            return data.decode("utf-8")
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Decryption failed for Case ID {self.id}: {e}")
            return encrypted_value  # Return the encrypted value if decryption fails

    def encrypt_fields(self):
        if hasattr(self, "encryption_key"):
            cipher = self.encryption_key.get_cipher()
        else:
            self._temp_key = os.urandom(32)
            self._temp_iv = os.urandom(16)
            cipher = Cipher(
                algorithms.AES(self._temp_key),
                modes.CBC(self._temp_iv),
                backend=default_backend(),
            )

        for field_name in [
            "case_title",
            "case_description",
            "case_category",
            "case_status_notes",
            "final_report",
            "conclusion",
        ]:
            value = getattr(self, field_name)
            if isinstance(value, str) and value:
                try:
                    encrypted_bytes = base64.b64decode(value)
                    decryptor = cipher.decryptor()
                    padded_data = (
                        decryptor.update(encrypted_bytes) + decryptor.finalize()
                    )
                    self._unpad_data(padded_data)
                    continue
                except Exception:
                    encrypted = self.encrypt_field_with_cipher(value, cipher)
                    setattr(self, field_name, encrypted)

    def save(self, *args, **kwargs):
        if not self.case_id:
            self.case_id = self.generate_case_id()
        self.encrypt_fields()
        super().save(*args, **kwargs)
        if hasattr(self, "_temp_key"):
            EncryptionKey.objects.create(
                case=self, key=self._temp_key, iv=self._temp_iv
            )
            delattr(self, "_temp_key")
            delattr(self, "_temp_iv")

    def get_title(self):
        return self.decrypt_field(self.case_title)

    def get_description(self):
        return self.decrypt_field(self.case_description)

    def get_category(self):
        return self.decrypt_field(self.case_category)

    def get_status_notes(self):
        return self.decrypt_field(self.case_status_notes)

    def get_final_report(self):
        return self.decrypt_field(self.final_report)

    def get_conclusion(self):
        return self.decrypt_field(self.conclusion)


class AssignmentRequest(models.Model):
    STATUS_CHOICES = [
        ("pending_creator", "Pending Creator Approval"),
        ("pending_admin", "Pending Admin Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    REQUEST_TYPE_CHOICES = [
        ("assignment", "Assignment"),
        ("handover", "Handover"),
    ]

    case = models.ForeignKey(
        Case, on_delete=models.CASCADE, related_name="assignment_requests"
    )
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    assigned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="assignment_requests"
    )
    request_type = models.CharField(
        max_length=20, choices=REQUEST_TYPE_CHOICES, default="assignment"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending_creator"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        title_preview = (
            self.case.case_title[:30] + "..."
            if self.case.case_title and len(self.case_title) > 30
            else self.case_title
        )
        return f"{self.request_type} for Case (Encrypted: {title_preview or 'N/A'}) by {self.requested_by}"


class InvestigatorCaseStatus(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="investigator_statuses")
    investigator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="case_statuses"
    )
    accepted = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    under_review = models.BooleanField(default=False)
    under_review_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['case', 'investigator']

    def __str__(self):
        return f"{self.investigator} - {self.case.get_title()} (Accepted: {self.accepted}, Under Review: {self.under_review})"


class CaseAuditLog(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="audit_logs", null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True, null=True)

    @classmethod
    def log_action(cls, user, case=None, action=None, details=None):
        cls.objects.create(user=user, case=case, action=action, details=details)

    def __str__(self):
        return f"[{self.timestamp}] {self.user} - {self.action} on case {self.case.case_id}"
