from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from cases.permissions import role_required
from cases.models import Case, CaseAuditLog
from evidence.models import Evidence, EvidenceAuditLog
from custody.models import CustodyLog, EvidenceStorage
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta


@login_required
@role_required("auditor")
def auditor_dashboard(request):
    """Auditor dashboard - overview of all audit activities"""
    # Get statistics
    total_cases = Case.objects.count()
    total_evidence = Evidence.objects.count()
    
    # Recent audit logs
    recent_audit_logs = EvidenceAuditLog.objects.select_related(
        'evidence', 'evidence__case', 'user'
    ).order_by('-timestamp')[:20]
    
    # Cases with recent activity
    recent_cases = Case.objects.select_related('created_by').order_by(
        '-date_created'
    )[:10]
    
    context = {
        'total_cases': total_cases,
        'total_evidence': total_evidence,
        'recent_audit_logs': recent_audit_logs,
        'recent_cases': recent_cases,
    }
    return render(request, 'auditor/dashboard.html', context)


@login_required
@role_required("auditor")
def audit_logs(request):
    """View all audit logs across the system"""
    # Get all case audit logs
    case_audit_logs = CaseAuditLog.objects.select_related(
        'case', 'user'
    ).order_by('-timestamp')
    
    # Get all evidence audit logs
    evidence_audit_logs = EvidenceAuditLog.objects.select_related(
        'evidence', 'evidence__case', 'user'
    ).order_by('-timestamp')
    
    # Get all custody logs
    custody_logs = CustodyLog.objects.select_related(
        'case', 'evidence', 'user'
    ).order_by('-timestamp')[:100]
    
    # Filter by type if specified
    log_type = request.GET.get('type')
    if log_type == 'case':
        logs = case_audit_logs
        log_source = 'case'
    elif log_type == 'evidence':
        logs = evidence_audit_logs
        log_source = 'evidence'
    elif log_type == 'custody':
        logs = custody_logs
        log_source = 'custody'
    else:
        # Combine all logs
        logs = list(case_audit_logs[:50]) + list(evidence_audit_logs[:50]) + list(custody_logs[:50])
        logs = sorted(logs, key=lambda x: x.timestamp, reverse=True)[:100]
        log_source = 'all'
    
    context = {
        'case_audit_logs': case_audit_logs[:50],
        'evidence_audit_logs': evidence_audit_logs[:50],
        'custody_logs': custody_logs,
        'logs': logs,
        'log_source': log_source,
    }
    return render(request, 'auditor/audit_logs.html', context)


@login_required
@role_required("auditor")
def case_audit_logs(request, case_id):
    """View audit logs for a specific case"""
    case = get_object_or_404(Case, case_id=case_id)
    
    # Get case audit logs
    case_logs = CaseAuditLog.objects.filter(case=case).select_related(
        'user'
    ).order_by('-timestamp')
    
    # Get evidence audit logs for this case
    evidence_audit_logs = EvidenceAuditLog.objects.filter(
        evidence__case=case
    ).select_related('evidence', 'user').order_by('-timestamp')
    
    # Get custody logs for this case
    custody_logs = CustodyLog.objects.filter(case=case).select_related(
        'evidence', 'user'
    ).order_by('-timestamp')
    
    context = {
        'case': case,
        'case_logs': case_logs,
        'evidence_audit_logs': evidence_audit_logs,
        'custody_logs': custody_logs,
    }
    return render(request, 'auditor/case_audit_logs.html', context)


@login_required
@role_required("auditor")
def chain_of_custody_report(request):
    """Chain of custody report - shows custody chain for all evidence"""
    # Get all evidence with their custody logs
    evidence_list = Evidence.objects.select_related(
        'case', 'uploaded_by'
    ).prefetch_related(
        'custody_logs__user',
        'custody_logs__from_location',
        'custody_logs__to_location',
        'storage'
    ).order_by('-date_uploaded')
    
    # Calculate statistics
    total_evidence = evidence_list.count()
    evidence_with_valid_metadata = evidence_list.filter(metadata_valid=True).count()
    evidence_with_issues = evidence_list.filter(metadata_valid=False).count()
    
    context = {
        'evidence_list': evidence_list,
        'total_evidence': total_evidence,
        'evidence_with_valid_metadata': evidence_with_valid_metadata,
        'evidence_with_issues': evidence_with_issues,
    }
    return render(request, 'auditor/chain_of_custody_report.html', context)


@login_required
@role_required("auditor")
def evidence_integrity_check(request):
    """Integrity check view - shows evidence integrity status"""
    # Get all evidence with integrity information
    evidence_list = Evidence.objects.select_related(
        'case', 'uploaded_by'
    ).order_by('-date_uploaded')
    
    # Count by status
    valid_evidence = evidence_list.filter(metadata_valid=True).count()
    invalid_evidence = evidence_list.filter(metadata_valid=False).count()
    pending_verification = evidence_list.filter(
        metadata_valid__isnull=True
    ).count()
    
    context = {
        'evidence_list': evidence_list,
        'valid_evidence': valid_evidence,
        'invalid_evidence': invalid_evidence,
        'pending_verification': pending_verification,
        'total_evidence': evidence_list.count(),
    }
    return render(request, 'auditor/integrity_check.html', context)


@login_required
@role_required("auditor")
def evidence_custody_history(request, evidence_id):
    """View detailed custody history for a specific evidence"""
    evidence = get_object_or_404(Evidence, id=evidence_id)
    
    # Get custody logs
    custody_logs = CustodyLog.objects.filter(
        evidence=evidence
    ).select_related(
        'user', 'from_location', 'to_location'
    ).order_by('-timestamp')
    
    # Get audit logs
    audit_logs = EvidenceAuditLog.objects.filter(
        evidence=evidence
    ).select_related('user').order_by('-timestamp')
    
    context = {
        'evidence': evidence,
        'custody_logs': custody_logs,
        'audit_logs': audit_logs,
    }
    return render(request, 'auditor/evidence_custody_history.html', context)


@login_required
@role_required("auditor")
def case_integrity_report(request, case_id):
    """Integrity report for a specific case"""
    case = get_object_or_404(Case, case_id=case_id)
    
    # Get all evidence for this case
    evidence_list = Evidence.objects.filter(
        case=case
    ).select_related('uploaded_by').order_by('-date_uploaded')
    
    valid_count = evidence_list.filter(metadata_valid=True).count()
    invalid_count = evidence_list.filter(metadata_valid=False).count()
    
    context = {
        'case': case,
        'evidence_list': evidence_list,
        'valid_count': valid_count,
        'invalid_count': invalid_count,
        'total_evidence': evidence_list.count(),
    }
    return render(request, 'auditor/case_integrity_report.html', context)
