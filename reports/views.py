from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from cases.permissions import role_required
from cases.models import Case
from evidence.models import Evidence
from .models import AnalysisReport
from .forms import AnalysisReportCreateForm, AnalysisReportReviewForm


@login_required
@role_required('analyst', 'admin')
def create_analysis_report(request, case_id, evidence_id=None):
    case = get_object_or_404(Case, case_id=case_id)
    evidence = None
    if evidence_id:
        evidence = get_object_or_404(Evidence, id=evidence_id, case=case)
    
    if request.method == 'POST':
        form = AnalysisReportCreateForm(request.POST, case=case, evidence=evidence)
        if form.is_valid():
            report = form.save(commit=False)
            report.case = case
            report.evidence = evidence
            report.created_by = request.user
            report.save()
            
            messages.success(request, 'Analysis report created successfully')
            if evidence:
                return redirect('evidence:view_evidence', evidence_id=evidence.id)
            return redirect('cases:view_case', case_id=case.case_id)
    else:
        form = AnalysisReportCreateForm(case=case, evidence=evidence)
    
    context = {
        'form': form,
        'case': case,
        'evidence': evidence
    }
    return render(request, 'reports/create_report.html', context)


@login_required
@role_required('analyst', 'investigator', 'admin', 'auditor')
def view_analysis_report(request, report_id):
    report = get_object_or_404(AnalysisReport, id=report_id)
    
    context = {
        'report': report
    }
    return render(request, 'reports/view_report.html', context)


@login_required
@role_required('analyst', 'admin')
def edit_analysis_report(request, report_id):
    report = get_object_or_404(AnalysisReport, id=report_id)
    
    if report.created_by != request.user and not request.user.is_superuser:
        messages.error(request, 'You can only edit your own reports')
        return redirect('reports:view_report', report_id=report.id)
    
    if report.status != 'draft':
        messages.error(request, 'You can only edit draft reports')
        return redirect('reports:view_report', report_id=report.id)
    
    if request.method == 'POST':
        form = AnalysisReportCreateForm(request.POST, case=report.case, evidence=report.evidence, instance=report)
        if form.is_valid():
            form.save()
            messages.success(request, 'Analysis report updated successfully')
            return redirect('reports:view_report', report_id=report.id)
    else:
        form = AnalysisReportCreateForm(case=report.case, evidence=report.evidence, instance=report)
    
    context = {
        'form': form,
        'report': report,
        'case': report.case,
        'evidence': report.evidence
    }
    return render(request, 'reports/edit_report.html', context)


@login_required
@role_required('analyst', 'admin')
def submit_analysis_report(request, report_id):
    report = get_object_or_404(AnalysisReport, id=report_id)
    
    if report.created_by != request.user and not request.user.is_superuser:
        messages.error(request, 'You can only submit your own reports')
        return redirect('reports:view_report', report_id=report.id)
    
    if report.status != 'draft':
        messages.error(request, 'You can only submit draft reports')
        return redirect('reports:view_report', report_id=report.id)
    
    report.status = 'submitted'
    report.save()
    
    messages.success(request, 'Analysis report submitted successfully')
    return redirect('reports:view_report', report_id=report.id)


@login_required
@role_required('admin')
def review_analysis_report(request, report_id):
    report = get_object_or_404(AnalysisReport, id=report_id)
    
    if report.status not in ['submitted', 'reviewed']:
        messages.error(request, 'You can only review submitted reports')
        return redirect('reports:view_report', report_id=report.id)
    
    if request.method == 'POST':
        form = AnalysisReportReviewForm(request.POST, instance=report)
        if form.is_valid():
            report = form.save(commit=False)
            report.reviewed_by = request.user
            report.reviewed_at = timezone.now()
            report.save()
            
            messages.success(request, 'Analysis report reviewed successfully')
            return redirect('reports:view_report', report_id=report.id)
    else:
        form = AnalysisReportReviewForm(instance=report)
    
    context = {
        'form': form,
        'report': report
    }
    return render(request, 'reports/review_report.html', context)


@login_required
@role_required('analyst', 'investigator', 'admin', 'auditor')
def case_reports_list(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)
    reports = AnalysisReport.objects.filter(case=case).order_by('-created_at')
    
    context = {
        'case': case,
        'reports': reports
    }
    return render(request, 'reports/case_reports.html', context)


@login_required
@role_required('analyst', 'investigator', 'admin', 'auditor')
def evidence_reports_list(request, evidence_id):
    evidence = get_object_or_404(Evidence, id=evidence_id)
    reports = AnalysisReport.objects.filter(evidence=evidence).order_by('-created_at')
    
    context = {
        'evidence': evidence,
        'reports': reports
    }
    return render(request, 'reports/evidence_reports.html', context)


@login_required
@role_required('analyst', 'admin')
def analyst_dashboard(request):
    my_reports = AnalysisReport.objects.filter(created_by=request.user).order_by('-created_at')
    draft_reports = my_reports.filter(status='draft')
    submitted_reports = my_reports.filter(status='submitted')
    total_submitted = submitted_reports.count()
    
    pending_review = AnalysisReport.objects.filter(status='submitted').order_by('-created_at')
    
    cases_in_analysis = Case.objects.filter(case_status='Approved & Assigned').order_by('-date_created')
    
    recent_evidence = Evidence.objects.filter(
        case__case_status='Approved & Assigned'
    ).select_related('case', 'uploaded_by').order_by('-date_uploaded')[:10]
    
    context = {
        'my_reports': my_reports[:10],
        'draft_reports': draft_reports,
        'submitted_reports': submitted_reports,
        'total_submitted': total_submitted,
        'pending_review': pending_review[:10],
        'cases_in_analysis': cases_in_analysis[:10],
        'recent_evidence': recent_evidence,
    }
    return render(request, 'reports/analyst_dashboard.html', context)


@login_required
@role_required('analyst')
def my_reports(request):
    """View all reports submitted by the analyst"""
    reports = AnalysisReport.objects.filter(
        created_by=request.user,
        status='submitted'
    ).select_related('case', 'evidence').order_by('-created_at')
    
    total_count = reports.count()
    
    context = {
        'reports': reports,
        'total_count': total_count,
    }
    return render(request, 'reports/my_reports.html', context)
