from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken
from django.core.files.base import ContentFile


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

    case_title = models.BinaryField(editable=True)
    case_description = models.BinaryField(editable=True)
    case_category = models.BinaryField(editable=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cases')
    case_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')
    case_status_notes = models.BinaryField(editable=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    invalid_reason = models.TextField(blank=True, null=True)
    withdraw_reason = models.TextField(blank=True, null=True)
    close_reason = models.TextField(blank=True, null=True)
    closure_approved = models.BooleanField(default=False)
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
    return cipher.encrypt(value.encode())

def decrypt_field(self, encrypted_value):
    """Decrypt text data."""
    if not encrypted_value:
        return ""
    try:
        cipher = self.encryption_key.get_cipher()
        return cipher.decrypt(encrypted_value).decode()
    except (InvalidToken, AttributeError) as e:
        # Handle decryption failure more gracefully
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Decryption failed for Case ID {self.id}: {e}")
        return "[Decryption Failed]"


    def encrypt_fields(self):
        """Encrypt all text fields before saving."""
        if not hasattr(self, 'encryption_key'):
            EncryptionKey.objects.create(case=self)

        if not isinstance(self.case_title, (bytes, bytearray)):
            self.case_title = self.encrypt_field(self.case_title)
        if not isinstance(self.case_description, (bytes, bytearray)):
            self.case_description = self.encrypt_field(self.case_description)
        if not isinstance(self.case_category, (bytes, bytearray)):
            self.case_category = self.encrypt_field(self.case_category)

    def save(self, *args, **kwargs):
        """Encrypt fields before saving."""
        self.encrypt_fields()
        super().save(*args, **kwargs)

    # ---------- Decryption Getters ----------
    def get_title(self):
        return self.decrypt_field(self.case_title)

    def get_description(self):
        return self.decrypt_field(self.case_description)

    def get_category(self):
        return self.decrypt_field(self.case_category)


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
    media = models.FileField(upload_to='case_media/')
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
            encrypted_file.name = self.media.name

            self.media.save(self.media.name, encrypted_file, save=False)
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
# 3. Case auditLog
# -----------------------------
class CaseAuditLog(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True, null=True)
    
    @classmethod
    def log_action(cls, user, case, action, details=None):
        cls.objects.create(user=user, case=case, action=action, details=details)
        
    def __str__(self):
        return f"[{self.timestamp}] {self.user} - {self.action} on case {self.case.id}"