from django.db import models
from django.conf import settings


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

    def __str__(self):
        return f"Evidence for Case {self.case.id} - {self.description}"


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
