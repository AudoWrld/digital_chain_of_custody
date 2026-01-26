from django.contrib import admin
from .models import Evidence, EvidenceAuditLog


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ['id', 'case', 'description', 'media_type', 'media_status', 'date_uploaded', 'uploaded_by']
    list_filter = ['media_type', 'media_status', 'date_uploaded']
    search_fields = ['description', 'case__case_title']
    readonly_fields = ['date_uploaded']


@admin.register(EvidenceAuditLog)
class EvidenceAuditLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'evidence', 'user', 'action', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['action', 'details', 'user__username']
    readonly_fields = ['timestamp']
