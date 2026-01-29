from django.db import models
from django.conf import settings
from cases.models import Case
from evidence.models import Evidence


class AnalysisReport(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('reviewed', 'Reviewed'),
        ('approved', 'Approved'),
    ]
    
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='analysis_reports')
    evidence = models.ForeignKey(Evidence, on_delete=models.CASCADE, related_name='analysis_reports', null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_reports')
    title = models.CharField(max_length=200)
    content = models.TextField()
    findings = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_reports')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Analysis Report'
        verbose_name_plural = 'Analysis Reports'
    
    def __str__(self):
        return f'{self.title} - {self.case.case_id}'
