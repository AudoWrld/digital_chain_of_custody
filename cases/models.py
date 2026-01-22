from django.db import models
from django.conf import settings
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
from django.core.files.base import ContentFile
from django.core.exceptions import ObjectDoesNotExist
import base64
import os
import hashlib


# -----------------------------
# 1. Encryption Key Model
# -----------------------------
class EncryptionKey(models.Model):
    """
    AES-256 Encryption Key Model for Case Encryption.
    
    Each case gets a unique 256-bit encryption key.
    The key is stored securely in the database.
    """
    case = models.OneToOneField('Case', on_delete=models.CASCADE, related_name='encryption_key', unique=True)
    key = models.BinaryField(editable=False)
    iv = models.BinaryField(null=True, editable=False)  # Initialization Vector for AES
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """Generate a unique AES-256 key and IV for each new case."""
        if not self.key:
            # Generate 256-bit (32 bytes) key
            self.key = os.urandom(32)
            # Generate 128-bit (16 bytes) IV
            self.iv = os.urandom(16)
        super().save(*args, **kwargs)

    def get_cipher(self):
        """Return an AES-256 cipher object."""
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.CBC(self.iv),
            backend=default_backend()
        )
        return cipher

    def __str__(self):
        return f"AES-256 encryption key for Case ID: {self.case.id}"


# -----------------------------
# 2. Case Model
# -----------------------------
class Case(models.Model):
    STATUS_CHOICES = [
    ('Open', 'Open'),
    ('Pending Admin Approval', 'Pending Admin Approval'),
    ('Under Review', 'Under Review'),
    ('Closed', 'Closed'),
    ('Archived', 'Archived'),
    ('Invalid', 'Invalid'),
    ('Withdrawn','Withdrawn'),
    ]


    PRIORITY_CHOICES = [
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
    ('critical', 'Critical'),
]
    CASE_CATEGORIES = [
        ('Murder','Murder'),
        ('Theft','Theft'),
        ('SexualAbuse','SexualAbuse'),
        ('Bullying','Bullying'),
        
    ]

    case_title = models.TextField()
    case_description = models.TextField()
    case_category = models.CharField(max_length=20, choices=CASE_CATEGORIES)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cases')
    case_status = models.CharField(max_length=200, choices=STATUS_CHOICES, default='Open')
    case_status_notes = models.TextField()
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    invalid_reason = models.TextField(blank=True, null=True)
    withdraw_reason = models.TextField(blank=True, null=True)
    close_reason = models.TextField(blank=True, null=True)
    closure_approved = models.BooleanField(default=False)
    closure_creator_approved = models.BooleanField(default=False)
    case_priority = models.CharField(max_length=10,choices=PRIORITY_CHOICES,default='medium')
    assigned_investigators = models.ManyToManyField(settings.AUTH_USER_MODEL,related_name='assigned_cases',blank=True)
    closure_requested = models.BooleanField(default=False)



    def __str__(self):
        # Show encrypted data in shell/admin, not decrypted
        title_preview = self.case_title[:30] + "..." if self.case_title and len(self.case_title) > 30 else self.case_title
        return f"Case (Encrypted: {title_preview or 'N/A'}) - {self.case_status}"

    # ---------- AES-256 Encryption ----------
    def _pad_data(self, data):
        """Apply PKCS7 padding to data."""
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()
        return padded_data

    def _unpad_data(self, padded_data):
        """Remove PKCS7 padding from data."""
        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()
        return data

    def encrypt_field(self, value):
        """Encrypt text data using AES-256-CBC."""
        if value is None or value == "":
            return None
        cipher = self.encryption_key.get_cipher()
        encryptor = cipher.encryptor()
        
        # Convert to bytes, pad, encrypt
        data = value.encode('utf-8')
        padded_data = self._pad_data(data)
        encrypted_bytes = encryptor.update(padded_data) + encryptor.finalize()
        
        return base64.b64encode(encrypted_bytes).decode()

    def encrypt_field_with_cipher(self, value, cipher):
        """Encrypt text data with given cipher."""
        if value is None or value == "":
            return None
        encryptor = cipher.encryptor()
        
        data = value.encode('utf-8')
        padded_data = self._pad_data(data)
        encrypted_bytes = encryptor.update(padded_data) + encryptor.finalize()
        
        return base64.b64encode(encrypted_bytes).decode()

    def decrypt_field(self, encrypted_value):
        """Decrypt text data using AES-256-CBC."""
        if not encrypted_value:
            return ""
        try:
            cipher = self.encryption_key.get_cipher()
            decryptor = cipher.decryptor()
            
            encrypted_bytes = base64.b64decode(encrypted_value)
            padded_data = decryptor.update(encrypted_bytes) + decryptor.finalize()
            data = self._unpad_data(padded_data)
            
            return data.decode('utf-8')
        except Exception as e:
            # Handle decryption failure gracefully
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Decryption failed for Case ID {self.id}: {e}")
            return encrypted_value  # Return the encrypted value if decryption fails


    def encrypt_fields(self):
        """Encrypt all text fields before saving using AES-256."""
        if hasattr(self, 'encryption_key'):
            cipher = self.encryption_key.get_cipher()
        else:
            # Generate key and IV for new case
            self._temp_key = os.urandom(32)
            self._temp_iv = os.urandom(16)
            cipher = Cipher(
                algorithms.AES(self._temp_key),
                modes.CBC(self._temp_iv),
                backend=default_backend()
            )

        for field_name in ['case_title', 'case_description', 'case_category', 'case_status_notes']:
            value = getattr(self, field_name)
            if isinstance(value, str) and value:
                # Check if already encrypted by attempting to decrypt
                try:
                    encrypted_bytes = base64.b64decode(value)
                    decryptor = cipher.decryptor()
                    padded_data = decryptor.update(encrypted_bytes) + decryptor.finalize()
                    self._unpad_data(padded_data)
                    # If no exception, it's already encrypted, skip
                    continue
                except Exception:
                    # Not encrypted or invalid, encrypt
                    encrypted = self.encrypt_field_with_cipher(value, cipher)
                    setattr(self, field_name, encrypted)

    def save(self, *args, **kwargs):
        """Encrypt fields before saving using AES-256."""
        self.encrypt_fields()
        super().save(*args, **kwargs)
        # Create encryption key for new cases
        if hasattr(self, '_temp_key'):
            EncryptionKey.objects.create(case=self, key=self._temp_key, iv=self._temp_iv)
            delattr(self, '_temp_key')
            delattr(self, '_temp_iv')

    # ---------- Decryption Getters ----------
    def get_title(self):
        return self.decrypt_field(self.case_title)

    def get_description(self):
        return self.decrypt_field(self.case_description)

    def get_category(self):
        return self.decrypt_field(self.case_category)

    def get_status_notes(self):
        return self.decrypt_field(self.case_status_notes)


# -----------------------------
# 3. Case Media (Evidence)
# -----------------------------
class CaseMedia(models.Model):
    """
    Case Media (Evidence) Model.
    
    Note: Media files are NOT encrypted. Only the Case model uses AES-256 encryption
    for sensitive metadata. Media files are stored as-is for performance and accessibility.
    """
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('document', 'Document'),
        ('text', 'Text'),
        ('other', 'Other'),
    ]

    MEDIA_STATUS_CHOICES = [
        ('Valid','Valid'),
        ('Invalid',"Invalid"),
        ('Archived','Archived')
    ]
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='evidence')
    media = models.FileField(max_length=500)
    description = models.CharField(max_length=255)
    media_type = models.CharField(max_length=50, choices=MEDIA_TYPE_CHOICES)
    date_uploaded = models.DateTimeField(auto_now_add=True)
    media_status = models.CharField(max_length=20, choices=MEDIA_STATUS_CHOICES, default='Valid')
    
    def __str__(self):
        # Show encrypted case title, not decrypted
        title_preview = self.case.case_title[:30] + "..." if self.case.case_title and len(self.case.case_title) > 30 else self.case.case_title
        return f"Media for Case (Encrypted: {title_preview or 'N/A'})"



# -----------------------------
# 4. Assignment Request
# -----------------------------
class AssignmentRequest(models.Model):
    STATUS_CHOICES = [
        ('pending_creator', 'Pending Creator Approval'),
        ('pending_admin', 'Pending Admin Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    REQUEST_TYPE_CHOICES = [
        ('assignment', 'Assignment'),
        ('handover', 'Handover'),
    ]

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='assignment_requests')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    assigned_users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='assignment_requests')
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES, default='assignment')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_creator')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        # Show encrypted case title, not decrypted
        title_preview = self.case.case_title[:30] + "..." if self.case.case_title and len(self.case.case_title) > 30 else self.case.case_title
        return f"{self.request_type} for Case (Encrypted: {title_preview or 'N/A'}) by {self.requested_by}"

# -----------------------------
# 5. Case Audit Log
# -----------------------------
class CaseAuditLog(models.Model):
    """
    Audit log for tracking all actions performed on cases and their media.

    Standards:
    - For case actions: action describes the verb (e.g., 'Created case'), details provides additional info.
    - For media actions: action describes the verb (e.g., 'Uploaded media'), details includes file info and changes.
    - All media-related logs include the file path in details for filtering.
    """
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True, null=True)

    @classmethod
    def log_action(cls, user, case, action, details=None):
        """
        Log an action for a case.

        Args:
            user: User performing the action
            case: Case the action relates to
            action: Verb describing the action
            details: Additional details, including media file paths for media actions
        """
        cls.objects.create(user=user, case=case, action=action, details=details)

    def __str__(self):
        return f"[{self.timestamp}] {self.user} - {self.action} on case {self.case.id}"