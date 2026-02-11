from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from cases.permissions import custodian_required, custodian_or_auditor_required
from cases.models import Case
from evidence.models import Evidence
from .models import (
    StorageLocation,
    EvidenceStorage,
    CustodyLog,
    CaseStorage,
    CustodianAssignment,
)


@login_required
@custodian_required
def custody_dashboard(request):
    """Custody dashboard - main page for custodians"""
    my_case_storages = CaseStorage.objects.filter(is_active=True).select_related("case")

    evidence_in_custody = EvidenceStorage.objects.select_related(
        "evidence", "storage_location"
    )

    recent_custody_logs = CustodyLog.objects.select_related(
        "evidence", "case", "user"
    ).order_by("-timestamp")[:10]

    total_evidence = Evidence.objects.count()
    evidence_with_storage = EvidenceStorage.objects.count()

    my_active_assignments = CustodianAssignment.objects.filter(
        custodian=request.user, is_active=True
    ).select_related("case_storage", "case_storage__case")

    context = {
        "my_case_storages": my_case_storages,
        "evidence_in_custody": evidence_in_custody[:10],
        "recent_custody_logs": recent_custody_logs,
        "total_evidence": total_evidence,
        "evidence_with_storage": evidence_with_storage,
        "my_case_storages_count": my_case_storages.count(),
        "my_active_assignments": my_active_assignments,
    }
    return render(request, "custody/custody_dashboard.html", context)


@login_required
@custodian_required
def case_storages_list(request):
    """Case storages list - shows all storages custodians can manage"""
    case_storages = CaseStorage.objects.filter(is_active=True).select_related("case")

    my_case_storages = CaseStorage.objects.filter(
        custodian_assignments__custodian=request.user,
        custodian_assignments__is_active=True,
        is_active=True,
    ).select_related("case")

    context = {
        "case_storages": case_storages,
        "my_case_storages": my_case_storages,
    }
    return render(request, "custody/case_storages.html", context)


@login_required
@custodian_required
def evidence_inventory(request):
    """Storage inventory page - shows storages custodians can manage"""
    case_storages = CaseStorage.objects.filter(is_active=True).select_related("case")

    context = {
        "case_storages": case_storages,
        "is_superuser": request.user.is_superuser,
    }
    return render(request, "custody/evidence_inventory.html", context)


@login_required
@custodian_required
def view_case_storage(request, case_id):
    """View case storage details"""
    case = get_object_or_404(Case, case_id=case_id)
    case_storage = get_object_or_404(CaseStorage, case=case)

    evidence_in_storage = EvidenceStorage.objects.filter(
        storage_location__case_storage=case_storage
    ).select_related("evidence", "storage_location")

    current_custodian = case_storage.current_custodian
    assignment_history = case_storage.custodian_assignments.all().select_related(
        "custodian", "assigned_by", "deactivated_by"
    )

    context = {
        "case": case,
        "case_storage": case_storage,
        "evidence_in_storage": evidence_in_storage,
        "current_custodian": current_custodian,
        "assignment_history": assignment_history,
    }
    return render(request, "custody/view_case_storage.html", context)


@login_required
@custodian_or_auditor_required
def evidence_custody_log(request, evidence_id):
    """Evidence custody log - audit trail for specific evidence"""
    evidence = get_object_or_404(Evidence, id=evidence_id)
    logs = CustodyLog.objects.filter(evidence=evidence).select_related(
        "user", "to_user", "from_location", "to_location"
    )

    context = {
        "evidence": evidence,
        "logs": logs,
    }
    return render(request, "custody/evidence_custody_log.html", context)


@login_required
@custodian_or_auditor_required
def case_custody_log(request, case_id):
    """Case custody log - audit trail for all evidence in a case"""
    case = get_object_or_404(Case, case_id=case_id)
    logs = CustodyLog.objects.filter(case=case).select_related(
        "evidence", "user", "to_user", "from_location", "to_location"
    )

    context = {
        "case": case,
        "logs": logs,
    }
    return render(request, "custody/case_custody_log.html", context)
