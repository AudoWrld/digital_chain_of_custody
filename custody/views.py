from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from cases.permissions import custodian_required, can_modify_custody
from cases.models import Case
from evidence.models import Evidence
from .models import CustodyTransfer, StorageLocation, EvidenceStorage, CustodyLog
from .forms import CustodyTransferRequestForm, CustodyTransferApprovalForm, StorageLocationForm, EvidenceStorageForm


@login_required
@custodian_required
def custody_dashboard(request):
    pending_transfers = CustodyTransfer.objects.filter(status='pending').select_related('evidence', 'from_user', 'to_user')
    my_transfers = CustodyTransfer.objects.filter(
        Q(from_user=request.user) | Q(to_user=request.user)
    ).select_related('evidence', 'from_user', 'to_user')
    
    storage_locations = StorageLocation.objects.filter(is_active=True)
    
    context = {
        'pending_transfers': pending_transfers,
        'my_transfers': my_transfers,
        'storage_locations': storage_locations,
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
def storage_locations_list(request):
    locations = StorageLocation.objects.all()
    
    context = {
        'locations': locations,
    }
    return render(request, 'custody/storage_locations.html', context)


@login_required
@custodian_required
def create_storage_location(request):
    if request.method == 'POST':
        form = StorageLocationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Storage location created successfully.')
            return redirect('custody:storage_locations')
    else:
        form = StorageLocationForm()
    
    context = {
        'form': form,
    }
    return render(request, 'custody/create_storage_location.html', context)


@login_required
@custodian_required
def edit_storage_location(request, location_id):
    location = get_object_or_404(StorageLocation, id=location_id)
    
    if request.method == 'POST':
        form = StorageLocationForm(request.POST, instance=location)
        if form.is_valid():
            form.save()
            messages.success(request, 'Storage location updated successfully.')
            return redirect('custody:storage_locations')
    else:
        form = StorageLocationForm(instance=location)
    
    context = {
        'form': form,
        'location': location,
    }
    return render(request, 'custody/edit_storage_location.html', context)


@login_required
@custodian_required
def assign_evidence_storage(request, evidence_id):
    evidence = get_object_or_404(Evidence, id=evidence_id)
    case = evidence.case
    
    storage_info, created = EvidenceStorage.objects.get_or_create(
        evidence=evidence,
        defaults={'stored_by': request.user}
    )
    
    if request.method == 'POST':
        form = EvidenceStorageForm(request.POST, instance=storage_info)
        if form.is_valid():
            storage_info = form.save(commit=False)
            storage_info.stored_by = request.user
            storage_info.save()
            
            CustodyLog.log_action(
                evidence=evidence,
                case=case,
                user=request.user,
                action='stored',
                details=f'Evidence stored at {storage_info.storage_location.name}',
                to_location=storage_info.storage_location
            )
            
            messages.success(request, 'Evidence storage assigned successfully.')
            return redirect('cases:view_case', case_id=case.case_id)
    else:
        form = EvidenceStorageForm(instance=storage_info)
    
    context = {
        'form': form,
        'evidence': evidence,
        'case': case,
        'storage_info': storage_info,
    }
    return render(request, 'custody/assign_storage.html', context)


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
