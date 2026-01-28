from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.http import JsonResponse
import json
from cases.models import Case, CaseAuditLog

try:
    from evidence.models import Evidence
    EVIDENCE_AVAILABLE = True
except ImportError:
    EVIDENCE_AVAILABLE = False

User = get_user_model()


@login_required
def dashboard(request):
    context = {
        'user_role': request.user.role if hasattr(request.user, 'role') else None,
        'is_superuser': request.user.is_superuser,
    }

    if request.user.is_superuser:
        case_status_counts = dict(Case.objects.values('case_status').annotate(count=Count('id')).values_list('case_status', 'count'))
        case_priority_counts = dict(Case.objects.values('case_priority').annotate(count=Count('id')).values_list('case_priority', 'count'))
        
        from django.db.models.functions import TruncDate
        from django.utils import timezone
        from datetime import timedelta
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        cases_by_date = list(Case.objects.filter(date_created__gte=thirty_days_ago).annotate(
            date=TruncDate('date_created')
        ).values('date').annotate(count=Count('id')).order_by('date'))
        
        cases_by_date_dict = {str(item['date']): item['count'] for item in cases_by_date}
        
        user_role_counts = dict(User.objects.values('role').annotate(count=Count('id')).values_list('role', 'count'))
        
        evidence_by_type = {}
        if EVIDENCE_AVAILABLE:
            total_evidence = Evidence.objects.count()
            valid_evidence = Evidence.objects.filter(media_status='Valid').count()
            invalid_evidence = Evidence.objects.filter(media_status='Invalid').count()
            evidence_by_type = dict(Evidence.objects.values('media_type').annotate(count=Count('id')).values_list('media_type', 'count'))
            
            context.update({
                'total_evidence': total_evidence,
                'valid_evidence': valid_evidence,
                'invalid_evidence': invalid_evidence,
            })
        else:
            context.update({
                'total_evidence': 0,
                'valid_evidence': 0,
                'invalid_evidence': 0,
            })
        
        pending_approval_cases = Case.objects.filter(case_status='Pending Admin Approval').count()
        cases_without_investigators = Case.objects.filter(assigned_investigators__isnull=True).count()
        unverified_users = User.objects.filter(verified=False).count()
        recent_users = User.objects.order_by('-date_joined')[:5]
        
        critical_cases_without_investigators = Case.objects.filter(
            case_priority='critical',
            case_status__in=['Open', 'Under Review'],
            assigned_investigators__isnull=True
        ).count()
        high_priority_cases = Case.objects.filter(case_priority='high', case_status__in=['Open', 'Under Review']).count()
        long_open_cases = Case.objects.filter(
            case_status='Open',
            date_created__lte=timezone.now() - timedelta(days=30)
        ).count()
        
        system_alerts = []
        if critical_cases_without_investigators > 0:
            system_alerts.append({
                'type': 'critical',
                'message': f'{critical_cases_without_investigators} critical cases require immediate attention',
                'icon': 'bx-error'
            })
        if pending_approval_cases > 0:
            system_alerts.append({
                'type': 'warning',
                'message': f'{pending_approval_cases} cases pending admin approval',
                'icon': 'bx-time'
            })
        if cases_without_investigators > 0:
            system_alerts.append({
                'type': 'warning',
                'message': f'{cases_without_investigators} cases without assigned investigators',
                'icon': 'bx-user-x'
            })
        if unverified_users > 0:
            system_alerts.append({
                'type': 'info',
                'message': f'{unverified_users} users awaiting verification',
                'icon': 'bx-user-plus'
            })
        if long_open_cases > 0:
            system_alerts.append({
                'type': 'warning',
                'message': f'{long_open_cases} cases open for more than 30 days',
                'icon': 'bx-time-five'
            })
        
        context.update({
            'total_cases': Case.objects.count(),
            'open_cases': Case.objects.filter(case_status='Open').count(),
            'under_review_cases': Case.objects.filter(case_status='Under Review').count(),
            'closed_cases': Case.objects.filter(case_status='Closed').count(),
            'total_users': User.objects.count(),
            'recent_cases': Case.objects.all().order_by('-date_created')[:5],
            'recent_audit_logs': CaseAuditLog.objects.all().order_by('-timestamp')[:5],
            'case_status_counts': json.dumps(case_status_counts),
            'case_priority_counts': json.dumps(case_priority_counts),
            'cases_by_date': json.dumps(cases_by_date_dict),
            'user_role_counts': json.dumps(user_role_counts),
            'evidence_by_type': json.dumps(evidence_by_type),
            'pending_approval_cases': pending_approval_cases,
            'cases_without_investigators': cases_without_investigators,
            'unverified_users': unverified_users,
            'recent_users': recent_users,
            'critical_cases': critical_cases_without_investigators,
            'high_priority_cases': high_priority_cases,
            'long_open_cases': long_open_cases,
            'system_alerts': system_alerts,
        })
    elif request.user.role == 'regular_user':
        user_cases = Case.objects.filter(created_by=request.user)
        context.update({
            'total_cases': user_cases.count(),
            'open_cases': user_cases.filter(case_status='Open').count(),
            'under_review_cases': user_cases.filter(case_status='Under Review').count(),
            'closed_cases': user_cases.filter(case_status='Closed').count(),
            'recent_cases': user_cases.order_by('-date_created')[:5],
            'recent_audit_logs': CaseAuditLog.objects.filter(
                case__created_by=request.user
            ).order_by('-timestamp')[:5],
        })
    elif request.user.role == 'investigator':
        assigned_cases = Case.objects.filter(assigned_investigators=request.user)
        context.update({
            'total_cases': assigned_cases.count(),
            'open_cases': assigned_cases.filter(case_status='Open').count(),
            'under_review_cases': assigned_cases.filter(case_status='Under Review').count(),
            'closed_cases': assigned_cases.filter(case_status='Closed').count(),
            'recent_cases': assigned_cases.order_by('-date_created')[:5],
            'recent_audit_logs': CaseAuditLog.objects.filter(
                case__assigned_investigators=request.user
            ).order_by('-timestamp')[:5],
        })
    elif request.user.role == 'analyst':
        context.update({
            'total_cases': Case.objects.count(),
            'open_cases': Case.objects.filter(case_status='Open').count(),
            'under_review_cases': Case.objects.filter(case_status='Under Review').count(),
            'closed_cases': Case.objects.filter(case_status='Closed').count(),
            'recent_cases': Case.objects.all().order_by('-date_created')[:5],
        })
    elif request.user.role == 'custodian':
        context.update({
            'total_cases': Case.objects.count(),
            'recent_cases': Case.objects.all().order_by('-date_created')[:5],
        })
    elif request.user.role == 'auditor':
        context.update({
            'total_cases': Case.objects.count(),
            'total_audit_logs': CaseAuditLog.objects.count(),
            'recent_audit_logs': CaseAuditLog.objects.all().order_by('-timestamp')[:10],
        })

    return render(request, "dashboard/dashboard.html", context)
