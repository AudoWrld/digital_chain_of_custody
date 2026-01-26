from django.db import models
from django.conf import settings
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
from django.core.files.base import ContentFile
import base64
import os
import hashlib


class Evidence(models.Model):
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('document', 'Document'),
        ('text', 'Text'),
        ('other', 'Other'),
    ]

    MEDIA_STATUS_CHOICES = [
        ('Valid', 'Valid'),
        ('Invalid', 'Invalid'),
        ('Archived', 'Archived')
    ]

    case = models.ForeignKey('cases.Case', on_delete=models.CASCADE, related_name='evidence')
    media = models.FileField(max_length=500)
    description = models.CharField(max_length=255)
    media_type = models.CharField(max_length=50, choices=MEDIA_TYPE_CHOICES)
    date_uploaded = models.DateTimeField(auto_now_add=True)
    media_status = models.CharField(max_length=20, choices=MEDIA_STATUS_CHOICES, default='Valid')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='uploaded_evidence')
    sha256_hash = models.CharField(max_length=64, editable=False, null=True)
    is_immutable = models.BooleanField(default=True, editable=False)

    def __str__(self):
        return f"Evidence for Case {self.case.id} - {self.description}"

    def _pad_data(self, data):
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()
        return padded_data

    def _unpad_data(self, padded_data):
        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()
        return data

    def compute_sha256(self, file_obj):
        sha256 = hashlib.sha256()
        for chunk in file_obj.chunks():
            sha256.update(chunk)
        file_obj.seek(0)
        return sha256.hexdigest()

    def encrypt_file(self, file_obj, cipher):
        encrypted_chunks = []
        for chunk in file_obj.chunks():
            padded_data = self._pad_data(chunk)
            encryptor = cipher.encryptor()
            encrypted_chunk = encryptor.update(padded_data) + encryptor.finalize()
            encrypted_chunks.append(encrypted_chunk)
        return b''.join(encrypted_chunks)

    def decrypt_file(self, encrypted_file, cipher):
        decryptor = cipher.decryptor()
        decrypted_data = decryptor.read()
        return self._unpad_data(decrypted_data)

    def save(self, *args, **kwargs):
        if self.media and not self.pk:
            file_obj = self.media
            self.sha256_hash = self.compute_sha256(file_obj)
            
            cipher = self.case.encryption_key.get_cipher()
            encrypted_data = self.encrypt_file(file_obj, cipher)
            
            encrypted_filename = f"encrypted_{file_obj.name}"
            self.media.save(encrypted_filename, ContentFile(encrypted_data), save=False)
        
        super().save(*args, **kwargs)

    def get_decrypted_file(self):
        cipher = self.case.encryption_key.get_cipher()
        with self.media.open('rb') as encrypted_file:
            decrypted_data = self.decrypt_file(encrypted_file, cipher)
        return ContentFile(decrypted_data, name=self.media.name.replace('encrypted_', ''))


class EvidenceAuditLog(models.Model):
    evidence = models.ForeignKey(Evidence, on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True, null=True)

    @classmethod
    def log_action(cls, user, evidence, action, details=None):
        cls.objects.create(user=user, evidence=evidence, action=action, details=details)

    def __str__(self):
        return f"[{self.timestamp}] {self.user} - {self.action} on evidence {self.evidence.id}"
