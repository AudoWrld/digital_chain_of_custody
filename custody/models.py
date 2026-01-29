from django.db import models
from django.contrib.auth import get_user_model
from cases.models import Case
from evidence.models import Evidence

User = get_user_model()


class CustodyTransfer(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]
    
    evidence = models.ForeignKey(Evidence, on_delete=models.CASCADE, related_name='custody_transfers')
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='custody_transfers_from')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='custody_transfers_to')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='custody_transfer_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reason = models.TextField()
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_custody_transfers')
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f'Custody Transfer: {self.evidence.description} from {self.from_user} to {self.to_user}'


class StorageLocation(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    location_type = models.CharField(max_length=50, choices=[
        ('physical', 'Physical Storage'),
        ('digital', 'Digital Storage'),
        ('cloud', 'Cloud Storage'),
    ])
    capacity = models.BigIntegerField(help_text='Capacity in bytes', null=True, blank=True)
    used_space = models.BigIntegerField(default=0, help_text='Used space in bytes')
    is_active = models.BooleanField(default=True)
    managed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='managed_storage_locations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
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
    evidence = models.OneToOneField(Evidence, on_delete=models.CASCADE, related_name='storage_info')
    storage_location = models.ForeignKey(StorageLocation, on_delete=models.SET_NULL, null=True, related_name='stored_evidence')
    stored_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='stored_evidence')
    stored_at = models.DateTimeField(auto_now_add=True)
    last_accessed = models.DateTimeField(null=True, blank=True)
    access_count = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-stored_at']
    
    def __str__(self):
        return f'Storage: {self.evidence.description} at {self.storage_location}'


class CustodyLog(models.Model):
    ACTION_CHOICES = [
        ('stored', 'Stored'),
        ('retrieved', 'Retrieved'),
        ('transferred', 'Transferred'),
        ('verified', 'Verified'),
        ('archived', 'Archived'),
        ('moved', 'Moved'),
    ]
    
    evidence = models.ForeignKey(Evidence, on_delete=models.CASCADE, related_name='custody_logs')
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='custody_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='custody_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    details = models.TextField(blank=True)
    from_location = models.ForeignKey(StorageLocation, on_delete=models.SET_NULL, null=True, blank=True, related_name='custody_logs_from')
    to_location = models.ForeignKey(StorageLocation, on_delete=models.SET_NULL, null=True, blank=True, related_name='custody_logs_to')
    to_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='custody_logs_received')
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f'{self.action}: {self.evidence.description} by {self.user}'
    
    @classmethod
    def log_action(cls, evidence, case, user, action, details='', from_location=None, to_location=None, to_user=None):
        return cls.objects.create(
            evidence=evidence,
            case=case,
            user=user,
            action=action,
            details=details,
            from_location=from_location,
            to_location=to_location,
            to_user=to_user
        )
