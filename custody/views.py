from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from cases.permissions import custodian_required, can_modify_custody
from cases.models import Case
from evidence.models import Evidence
from .models import CustodyTransfer, StorageLocation, EvidenceStorage, CustodyLog, CaseStorage, CustodianAssignment
from .forms import CustodyTransferRequestForm, CustodyTransferApprovalForm, StorageLocationForm, EvidenceStorageForm


@login_required
@custodian_required
def custody_dashboard(request):
    pending_transfers = CustodyTransfer.objects.filter(status='pending').select_related('evidence', 'from_user', 'to_user')
    my_transfers = CustodyTransfer.objects.filter(
        Q(from_user=request.user) | Q(to_user=request.user)
    ).select_related('evidence', 'from_user', 'to_user')
    
    my_case_storages = CaseStorage.objects.filter(
        custodian_assignments__custodian=request.user,
        custodian_assignments__is_active=True,
        is_active=True
    ).select_related('case')
    
    evidence_in_custody = EvidenceStorage.objects.select_related('evidence', 'storage_location')
    
    recent_custody_logs = CustodyLog.objects.select_related('evidence', 'case', 'user').order_by('-timestamp')[:10]
    
    total_evidence = Evidence.objects.count()
    evidence_with_storage = EvidenceStorage.objects.count()
    
    my_active_assignments = CustodianAssignment.objects.filter(
        custodian=request.user,
        is_active=True
    ).select_related('case_storage', 'case_storage__case')
    
    context = {
        'pending_transfers': pending_transfers[:10],
        'my_transfers': my_transfers[:10],
        'my_case_storages': my_case_storages,
        'evidence_in_custody': evidence_in_custody[:10],
        'recent_custody_logs': recent_custody_logs,
        'total_evidence': total_evidence,
        'evidence_with_storage': evidence_with_storage,
        'pending_transfers_count': pending_transfers.count(),
        'my_transfers_count': my_transfers.count(),
        'my_case_storages_count': my_case_storages.count(),
        'my_active_assignments': my_active_assignments,
    }
    return render(request, 'custody/custody_dashboard.html', context)


@login_required
@can_modify_custody
def request_custody_transfer(request, evidence_id):
    evidence = get_object_or_404(Evidence, id=evidence_id)
    case = evidence.case
    
    if request.method == 'POST':
        form = CustodyTransferRequestForm(request.POST, evidence=evidence, from_user=request.user)
        if form.is_valid():
            transfer = form.save(commit=False)
            transfer.evidence = evidence
            transfer.from_user = request.user
            transfer.requested_by = request.user
            transfer.save()
            
            CustodyLog.log_action(
                evidence=evidence,
                case=case,
                user=request.user,
                action='transferred',
                details=f'Custody transfer requested from {request.user} to {transfer.to_user}. Reason: {transfer.reason}'
            )
            
            messages.success(request, 'Custody transfer request submitted successfully.')
            return redirect('cases:view_case', case_id=case.case_id)
    else:
        form = CustodyTransferRequestForm(evidence=evidence, from_user=request.user)
    
    context = {
        'form': form,
        'evidence': evidence,
        'case': case,
    }
    return render(request, 'custody/request_transfer.html', context)


@login_required
@custodian_required
def approve_custody_transfer(request, transfer_id):
    transfer = get_object_or_404(CustodyTransfer, id=transfer_id)
    
    if transfer.status != 'pending':
        messages.error(request, 'This transfer has already been processed.')
        return redirect('custody:dashboard')
    
    if request.method == 'POST':
        form = CustodyTransferApprovalForm(request.POST, instance=transfer)
        if form.is_valid():
            transfer = form.save(commit=False)
            transfer.approved_by = request.user
            transfer.approved_at = timezone.now()
            
            if transfer.status == 'approved':
                transfer.completed_at = timezone.now()
                
                evidence = transfer.evidence
                case = evidence.case
                
                CustodyLog.log_action(
                    evidence=evidence,
                    case=case,
                    user=request.user,
                    action='transferred',
                    details=f'Custody transferred from {transfer.from_user} to {transfer.to_user}. Approved by {request.user}.',
                    to_user=transfer.to_user
                )
                
                messages.success(request, 'Custody transfer approved and completed successfully.')
            elif transfer.status == 'rejected':
                CustodyLog.log_action(
                    evidence=transfer.evidence,
                    case=transfer.evidence.case,
                    user=request.user,
                    action='transferred',
                    details=f'Custody transfer from {transfer.from_user} to {transfer.to_user} rejected by {request.user}.'
                )
                messages.warning(request, 'Custody transfer rejected.')
            
            transfer.save()
            return redirect('custody:dashboard')
    else:
        form = CustodyTransferApprovalForm(instance=transfer)
    
    context = {
        'form': form,
        'transfer': transfer,
    }
    return render(request, 'custody/approve_transfer.html', context)


@login_required
@custodian_required
def case_storages_list(request):
    case_storages = CaseStorage.objects.filter(is_active=True).select_related('case')
    
    my_case_storages = CaseStorage.objects.filter(
        custodian_assignments__custodian=request.user,
        custodian_assignments__is_active=True,
        is_active=True
    ).select_related('case')
    
    context = {
        'case_storages': case_storages,
        'my_case_storages': my_case_storages,
    }
    return render(request, 'custody/case_storages.html', context)


@login_required
@custodian_required
def evidence_inventory(request):
    """Evidence inventory page with table like case_list"""
    # Get all evidence in storage
    evidence_storages = EvidenceStorage.objects.select_related(
        'evidence', 'evidence__case', 'storage_location', 'storage_location__case_storage'
    ).all()
    
    context = {
        'evidence_storages': evidence_storages,
        'is_superuser': request.user.is_superuser,
    }
    return render(request, 'custody/evidence_inventory.html', context)


@login_required
@custodian_required
def custody_transfers(request):
    """Custody transfers list page"""
    pending_transfers = CustodyTransfer.objects.filter(
        status='pending'
    ).select_related('evidence', 'evidence__case', 'from_user', 'to_user').order_by('-created_at')
    
    my_pending_transfers = CustodyTransfer.objects.filter(
        Q(from_user=request.user) | Q(to_user=request.user),
        status='pending'
    ).select_related('evidence', 'evidence__case', 'from_user', 'to_user').order_by('-created_at')
    
    context = {
        'pending_transfers': pending_transfers,
        'my_pending_transfers': my_pending_transfers,
    }
    return render(request, 'custody/custody_transfers.html', context)


@login_required
@custodian_required
def view_case_storage(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)
    case_storage = get_object_or_404(CaseStorage, case=case)
    
    evidence_in_storage = EvidenceStorage.objects.filter(
        storage_location__case_storage=case_storage
    ).select_related('evidence', 'storage_location')
    
    current_custodian = case_storage.current_custodian
    assignment_history = case_storage.custodian_assignments.all().select_related('custodian', 'assigned_by', 'deactivated_by')
    
    context = {
        'case': case,
        'case_storage': case_storage,
        'evidence_in_storage': evidence_in_storage,
        'current_custodian': current_custodian,
        'assignment_history': assignment_history,
    }
    return render(request, 'custody/view_case_storage.html', context)


@login_required
@custodian_required
def evidence_custody_log(request, evidence_id):
    evidence = get_object_or_404(Evidence, id=evidence_id)
    logs = CustodyLog.objects.filter(evidence=evidence).select_related('user', 'to_user', 'from_location', 'to_location')
    
    context = {
        'evidence': evidence,
        'logs': logs,
    }
    return render(request, 'custody/evidence_custody_log.html', context)


@login_required
@custodian_required
def case_custody_log(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)
    logs = CustodyLog.objects.filter(case=case).select_related('evidence', 'user', 'to_user', 'from_location', 'to_location')
    
    context = {
        'case': case,
        'logs': logs,
    }
    return render(request, 'custody/case_custody_log.html', context)
