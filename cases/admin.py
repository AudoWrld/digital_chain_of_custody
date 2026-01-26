from django.contrib import admin
from .models import Case, EncryptionKey, AssignmentRequest, CaseAuditLog


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_title', 'case_status', 'case_priority', 'date_created', 'created_by']
    list_filter = ['case_status', 'case_priority', 'date_created']
    search_fields = ['case_title', 'case_description', 'created_by__username']
    readonly_fields = ['date_created', 'last_modified']


@admin.register(EncryptionKey)
class EncryptionKeyAdmin(admin.ModelAdmin):
    list_display = ['id', 'case', 'created_at']
    readonly_fields = ['created_at']


@admin.register(AssignmentRequest)
class AssignmentRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'case', 'requested_by', 'request_type', 'status', 'created_at']
    list_filter = ['request_type', 'status', 'created_at']
    search_fields = ['case__case_title', 'requested_by__username']
    readonly_fields = ['created_at', 'approved_at']


@admin.register(CaseAuditLog)
class CaseAuditLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'case', 'user', 'action', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['action', 'details', 'user__username']
    readonly_fields = ['timestamp']