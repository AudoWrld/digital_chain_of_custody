from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from cases.models import Case, CaseAuditLog


@login_required
def dashboard(request):
    context = {
        'user_role': request.user.role if hasattr(request.user, 'role') else None,
        'is_superuser': request.user.is_superuser,
    }

    if request.user.is_superuser:
        context.update({
            'total_cases': Case.objects.count(),
            'open_cases': Case.objects.filter(case_status='Open').count(),
            'under_review_cases': Case.objects.filter(case_status='Under Review').count(),
            'closed_cases': Case.objects.filter(case_status='Closed').count(),
            'total_users': 0,
            'recent_cases': Case.objects.all().order_by('-date_created')[:5],
            'recent_audit_logs': CaseAuditLog.objects.all().order_by('-timestamp')[:5],
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
