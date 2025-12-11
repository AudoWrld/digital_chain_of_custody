from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken
from django.core.files.base import ContentFile
from django.core.exceptions import ObjectDoesNotExist
import base64


# -----------------------------
# 1. Encryption Key Model
# -----------------------------
class EncryptionKey(models.Model):
    case = models.OneToOneField('Case', on_delete=models.CASCADE, related_name='encryption_key', unique=True)
    key = models.BinaryField(editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """Generate a key automatically when a new case is created."""
        if not self.key:
            self.key = Fernet.generate_key()
        super().save(*args, **kwargs)

    def get_cipher(self):
        """Return a Fernet cipher object."""
        return Fernet(self.key)

    def __str__(self):
        return f"Encryption key for Case ID: {self.case.id}"


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
        return f"Case ({self.get_title() or 'Encrypted'}) - {self.case_status}"

    # ---------- Encryption ----------
    def encrypt_field(self, value):
        """Encrypt text data."""
        if value is None or value == "":
            return None
        cipher = self.encryption_key.get_cipher()
        encrypted_bytes = cipher.encrypt(value.encode())
        return base64.b64encode(encrypted_bytes).decode()

    def encrypt_field_with_cipher(self, value, cipher):
        """Encrypt text data with given cipher."""
        if value is None or value == "":
            return None
        encrypted_bytes = cipher.encrypt(value.encode())
        return base64.b64encode(encrypted_bytes).decode()

    def decrypt_field(self, encrypted_value):
        """Decrypt text data."""
        if not encrypted_value:
            return ""
        try:
            cipher = self.encryption_key.get_cipher()
            encrypted_bytes = base64.b64decode(encrypted_value)
            return cipher.decrypt(encrypted_bytes).decode()
        except Exception as e:
            # Handle decryption failure more gracefully
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Decryption failed for Case ID {self.id}: {e}")
            return encrypted_value  # Return the encrypted value if decryption fails


    def encrypt_fields(self):
        """Encrypt all text fields before saving."""
        if hasattr(self, 'encryption_key'):
            cipher = self.encryption_key.get_cipher()
        else:
            # Generate key for new case
            self._temp_key = Fernet.generate_key()
            cipher = Fernet(self._temp_key)

        for field_name in ['case_title', 'case_description', 'case_category', 'case_status_notes']:
            value = getattr(self, field_name)
            if isinstance(value, str) and value:
                # Check if already encrypted
                try:
                    encrypted_bytes = base64.b64decode(value)
                    cipher.decrypt(encrypted_bytes)
                    # If no exception, it's already encrypted, skip
                    continue
                except Exception:
                    # Not encrypted or invalid, encrypt
                    encrypted = self.encrypt_field_with_cipher(value, cipher)
                    setattr(self, field_name, encrypted)

    def save(self, *args, **kwargs):
        """Encrypt fields before saving."""
        self.encrypt_fields()
        super().save(*args, **kwargs)
        # Create encryption key for new cases
        if hasattr(self, '_temp_key'):
            EncryptionKey.objects.create(case=self, key=self._temp_key)
            delattr(self, '_temp_key')

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
    _encrypted = False  # flag to avoid double-encryption in one save cycle
    media_status = models.CharField(max_length=20, choices=MEDIA_STATUS_CHOICES, default='Valid')
    
    

    def __str__(self):
        return f"Media for Case: {self.case.get_title()}"

    def save(self, *args, **kwargs):
        """Encrypt media files before saving."""
        if not self.case.encryption_key:
            EncryptionKey.objects.create(case=self.case)

        cipher = self.case.encryption_key.get_cipher()

        if self.media and not self._encrypted:
            self.media.open('rb')
            file_content = self.media.read()
            self.media.close()

            encrypted_content = cipher.encrypt(file_content)
            encrypted_file = ContentFile(encrypted_content)
            # Ensure path is case_media/filename, extract filename from any existing path
            filename = self.media.name.split('/')[-1]
            encrypted_file.name = f'case_media/{filename}'

            self.media.save(encrypted_file.name, encrypted_file, save=False)
            self._encrypted = True

        super().save(*args, **kwargs)

    def decrypt_media(self):
        """Return decrypted media content."""
        cipher = self.case.encryption_key.get_cipher()
        self.media.open('rb')
        encrypted_content = self.media.read()
        self.media.close()
        decrypted_content = cipher.decrypt(encrypted_content)
        return decrypted_content

    def download_decrypted(self):
        """Generate a decrypted version of the file for authorized download."""
        decrypted_content = self.decrypt_media()
        file_name = f"decrypted_{self.media.name.split('/')[-1]}"
        return ContentFile(decrypted_content, name=file_name)



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
        return f"{self.request_type} for {self.case.get_title()} by {self.requested_by}"

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