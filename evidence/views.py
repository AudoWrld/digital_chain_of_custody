from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, FileResponse, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from cases.permissions import role_required, can_upload_evidence
from cases.models import Case
from .models import Evidence, EvidenceAuditLog
from .forms import EvidenceUploadForm
from custody.models import CaseStorage, EvidenceStorage, CustodyLog
import json
import mimetypes


@login_required
@can_upload_evidence
def upload_evidence(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)

    if request.method == "POST":
        form = EvidenceUploadForm(request.POST, request.FILES)
        if form.is_valid():
            evidence = form.save(commit=False)
            evidence.case = case
            evidence.uploaded_by = request.user
            evidence.original_filename = form.cleaned_data["media"].name
            evidence.media_type = form.cleaned_data.get("media_type", "other")
            evidence.save()

            EvidenceAuditLog.log_action(
                user=request.user,
                evidence=evidence,
                action="Evidence Uploaded",
                details=f"File: {evidence.original_filename}, SHA256: {evidence.sha256_hash}",
            )

            case_storage = getattr(case, "storage", None)
            if case_storage:
                storage_location = case_storage.storage_locations.first()
                if storage_location:
                    EvidenceStorage.objects.create(
                        evidence=evidence, storage_location=storage_location
                    )

                    from custody.models import StorageLog

                    StorageLog.log_action(
                        case_storage,
                        request.user,
                        "upload",
                        f"Evidence {evidence.original_filename} uploaded to {case_storage.storage_name}",
                    )

                    CustodyLog.log_action(
                        case=case,
                        evidence=evidence,
                        user=request.user,
                        action="stored",
                        details=f"Evidence {evidence.original_filename} stored in {case_storage.storage_name}",
                    )

            if not evidence.metadata_valid:
                messages.warning(
                    request,
                    f'Evidence uploaded but metadata validation failed: {", ".join(evidence.metadata_issues)}',
                )
            else:
                messages.success(
                    request, "Evidence uploaded successfully with valid metadata"
                )

            return redirect("cases:view_case", case_id=case.case_id)
    else:
        form = EvidenceUploadForm()

    return render(
        request, "evidence/upload_evidence.html", {"form": form, "case": case}
    )


@login_required
@role_required("investigator", "analyst", "admin", "auditor", "regular_user")
def view_evidence(request, evidence_id):
    evidence = get_object_or_404(Evidence, id=evidence_id)

    if request.user.role == 'regular_user':
        if request.user != evidence.case.created_by:
            return HttpResponseForbidden("You are not allowed to view this evidence!")
    
    audit_logs = EvidenceAuditLog.objects.filter(evidence=evidence).order_by(
        "-timestamp"
    )

    CustodyLog.log_action(
        evidence=evidence,
        case=evidence.case,
        user=request.user,
        action="viewed",
        details=f"Evidence viewed by {request.user.get_full_name()}",
    )

    return render(
        request,
        "evidence/view_evidence.html",
        {"evidence": evidence, "audit_logs": audit_logs},
    )


@login_required
@role_required("auditor")
def audit_evidence(request, evidence_id):
    evidence = get_object_or_404(Evidence, id=evidence_id)

    audit_logs = EvidenceAuditLog.objects.filter(evidence=evidence).order_by(
        "-timestamp"
    )

    CustodyLog.log_action(
        evidence=evidence,
        case=evidence.case,
        user=request.user,
        action="verified",
        details=f"Evidence audited by {request.user.get_full_name()}",
    )

    return render(
        request,
        "evidence/audit_evidence.html",
        {"evidence": evidence, "audit_logs": audit_logs},
    )


@login_required
@require_http_methods(["GET"])
@role_required("investigator", "analyst", "admin", "auditor")
def evidence_metadata_api(request, evidence_id):
    evidence = get_object_or_404(Evidence, id=evidence_id)

    return JsonResponse(
        {
            "id": evidence.id,
            "description": evidence.description,
            "media_type": evidence.media_type,
            "sha256_hash": evidence.sha256_hash,
            "md5_hash": evidence.md5_hash,
            "original_filename": evidence.original_filename,
            "metadata_valid": evidence.metadata_valid,
            "metadata_issues": evidence.metadata_issues,
            "metadata": evidence.metadata,
            "date_uploaded": evidence.date_uploaded.isoformat(),
            "uploaded_by": (
                evidence.uploaded_by.username if evidence.uploaded_by else None
            ),
        }
    )


@login_required
@require_http_methods(["GET"])
@role_required("investigator", "analyst", "admin", "auditor")
def case_evidence_list_api(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)

    evidence_list = Evidence.objects.filter(case=case).order_by("-date_uploaded")

    data = []
    for evidence in evidence_list:
        data.append(
            {
                "id": evidence.id,
                "description": evidence.description,
                "media_type": evidence.media_type,
                "sha256_hash": evidence.sha256_hash,
                "original_filename": evidence.original_filename,
                "metadata_valid": evidence.metadata_valid,
                "media_status": evidence.media_status,
                "date_uploaded": evidence.date_uploaded.isoformat(),
                "uploaded_by": (
                    evidence.uploaded_by.username if evidence.uploaded_by else None
                ),
            }
        )

    return JsonResponse({"evidence": data})


@login_required
@role_required("analyst")
def analyze_evidence(request, evidence_id):
    evidence = get_object_or_404(Evidence, id=evidence_id)

    if request.method == "POST":
        notes = request.POST.get("notes", "")
        findings = request.POST.get("findings", "")

        EvidenceAuditLog.log_action(
            user=request.user,
            evidence=evidence,
            action="Evidence Analyzed",
            details=f"Notes: {notes}, Findings: {findings}",
        )

        CustodyLog.log_action(
            evidence=evidence,
            case=evidence.case,
            user=request.user,
            action="verified",
            details=f"Evidence analyzed by {request.user.get_full_name()}. Findings: {findings}",
        )

        messages.success(request, "Evidence analysis logged")
        return redirect("evidence:view", evidence_id=evidence.id)

    return render(request, "evidence/analyze_evidence.html", {"evidence": evidence})


@login_required
@role_required("analyst", "admin")
def verify_evidence_integrity(request, evidence_id):
    evidence = get_object_or_404(Evidence, id=evidence_id)

    CustodyLog.log_action(
        evidence=evidence,
        case=evidence.case,
        user=request.user,
        action="verified",
        details=f"Evidence integrity verified by {request.user.get_full_name()}",
    )

    return render(request, "evidence/verify_evidence.html", {"evidence": evidence})


@login_required
@role_required("investigator", "analyst", "admin", "auditor", "regular_user")
def view_evidence_file(request, evidence_id):
    evidence = get_object_or_404(Evidence, id=evidence_id)

    # Check if user is case owner (regular user) - allow view access
    if request.user.role == 'regular_user':
        if request.user != evidence.case.created_by:
            return HttpResponseForbidden("You are not allowed to view this evidence file!")
    
    try:
        decrypted_file = evidence.get_decrypted_file()

        content_type, _ = mimetypes.guess_type(evidence.original_filename)
        if content_type is None:
            content_type = "application/octet-stream"

        response = FileResponse(decrypted_file, content_type=content_type)

        response["Content-Disposition"] = (
            f'inline; filename="{evidence.original_filename}"'
        )

        EvidenceAuditLog.log_action(
            user=request.user,
            evidence=evidence,
            action="Evidence Viewed",
            details=f"File: {evidence.original_filename}",
        )

        evidence_storage = getattr(evidence, "storage", None)
        if evidence_storage:
            evidence_storage.record_access(request.user)

        return response
    except Exception as e:
        messages.error(request, f"Error viewing evidence: {str(e)}")
        return redirect("evidence:view", evidence_id=evidence.id)


@login_required
@role_required("investigator", "analyst", "admin", "auditor", "regular_user")
def download_evidence_file(request, evidence_id):
    evidence = get_object_or_404(Evidence, id=evidence_id)

    if request.user.role == 'regular_user':
        if request.user != evidence.case.created_by:
            return HttpResponseForbidden("You are not allowed to download this evidence!")
    
    try:
        decrypted_file = evidence.get_decrypted_file()

        content_type, _ = mimetypes.guess_type(evidence.original_filename)
        if content_type is None:
            content_type = "application/octet-stream"

        response = FileResponse(decrypted_file, content_type=content_type)

        response["Content-Disposition"] = (
            f'attachment; filename="{evidence.original_filename}"'
        )

        EvidenceAuditLog.log_action(
            user=request.user,
            evidence=evidence,
            action="Evidence Downloaded",
            details=f"File: {evidence.original_filename}",
        )

        CustodyLog.log_action(
            evidence=evidence,
            case=evidence.case,
            user=request.user,
            action="downloaded",
            details=f"Evidence downloaded by {request.user.get_full_name()}",
        )

        evidence_storage = getattr(evidence, "storage", None)
        if evidence_storage:
            evidence_storage.record_access(request.user)

        return response
    except Exception as e:
        messages.error(request, f"Error downloading evidence: {str(e)}")
        return redirect("evidence:view", evidence_id=evidence.id)


@login_required
@role_required("admin", "auditor")
def all_evidence(request):
    evidence_list = Evidence.objects.select_related('case', 'uploaded_by').all().order_by("-date_uploaded")
    
    return render(
        request,
        "evidence/all_evidence.html",
        {"evidence_list": evidence_list, "is_superuser": request.user.is_superuser}
    )


@login_required
def my_evidence(request):
    if request.user.role == 'regular_user':
        evidence_list = Evidence.objects.select_related('case', 'uploaded_by').filter(
            case__created_by=request.user
        ).order_by("-date_uploaded")
    elif request.user.role == 'investigator':
        evidence_list = Evidence.objects.select_related('case', 'uploaded_by').filter(
            uploaded_by=request.user
        ).order_by("-date_uploaded")
    else:
        evidence_list = Evidence.objects.select_related('case', 'uploaded_by').filter(
            case__created_by=request.user
        ).order_by("-date_uploaded")
    
    return render(
        request,
        "evidence/my_evidence.html",
        {"evidence_list": evidence_list}
    )
