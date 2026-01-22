from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseForbidden, FileResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.files.base import ContentFile
from django.db.models import Q
from django.utils import timezone
from .models import Case, CaseMedia, EncryptionKey, CaseAuditLog, AssignmentRequest
from .forms import CaseForm, CaseMediaForm, EditCaseForm
from .permissions import regular_user_required, role_required
import csv
from django.contrib.auth import get_user_model
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@login_required
def case_list(request):
    if request.user.is_superuser:
        cases = Case.objects.all().select_related("encryption_key")
        is_superuser = True
    elif request.user.role == 'regular_user':
        cases = Case.objects.filter(
            created_by=request.user
        ).select_related("encryption_key")
        is_superuser = False
    elif request.user.role == 'investigator':
        cases = Case.objects.filter(
            assigned_investigators=request.user
        ).select_related("encryption_key")
        is_superuser = False
    else:
        return HttpResponseForbidden("You do not have permission to view cases.")

    return render(
        request, "cases/case_list.html", {"cases": cases, "is_superuser": is_superuser}
    )


@login_required
def assigned_cases(request):
    if request.user.is_superuser:
        cases = Case.objects.all().select_related("encryption_key")
        is_superuser = True
    elif request.user.role == 'investigator':
        cases = Case.objects.filter(
            assigned_investigators=request.user
        ).select_related("encryption_key")
        is_superuser = False
    else:
        return HttpResponseForbidden("Only investigators can view assigned cases.")

    return render(
        request, "cases/case_list.html", {"cases": cases, "is_superuser": is_superuser}
    )


@regular_user_required
def create_case(request):
    if request.method == "POST":
        form = CaseForm(request.POST)
        if form.is_valid():
            try:
                case = form.save(commit=False)
                case.created_by = request.user
                case.save()
                CaseAuditLog.log_action(
                    user=request.user, case=case, action="Created case"
                )

                messages.success(request, "Case created successfully!")
                return redirect("cases:view_case", case_id=case.id)
            except Exception as e:
                logger.error(f"Error creating case: {e}")
                messages.error(request, "Failed to create case. Please try again.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CaseForm()

    return render(request, "cases/create_case.html", {"form": form})


@login_required
def view_case(request, case_id):
    case = get_object_or_404(Case, id=case_id)

    if (
        request.user != case.created_by
        and request.user not in case.assigned_investigators.all()
        and not request.user.is_staff
    ):
        return HttpResponseForbidden("You are not allowed to view this case!")

    if request.method == "POST" and request.user.is_staff:
        action = request.POST.get("action")
        if action == "approve":
            request_id = request.POST.get("request_id")
            request_obj = get_object_or_404(AssignmentRequest, id=request_id, case=case)
            if request_obj.status == "pending_admin":
                request_obj.status = "approved"
                request_obj.approved_at = timezone.now()
                request_obj.save()
                case.assigned_investigators.set(request_obj.assigned_users.all())
                case.case_status = "Under Review"
                case.save()
                CaseAuditLog.log_action(
                    user=request.user,
                    case=case,
                    action="Approved investigator assignment",
                    details=f"Investigators: {list(request_obj.assigned_users.values_list('username', flat=True))}",
                )
        elif action == "reject":
            request_id = request.POST.get("request_id")
            request_obj = get_object_or_404(AssignmentRequest, id=request_id, case=case)
            request_obj.status = "rejected"
            request_obj.save()
            case.case_status = "Open"
            case.save()
            CaseAuditLog.log_action(
                user=request.user,
                case=case,
                action="Rejected investigator assignment",
                details=f"Request by {request_obj.requested_by.username}",
            )
        elif action == "assign_direct":
            investigators = request.POST.getlist("direct_investigators")
            case.assigned_investigators.set(investigators)
            case.case_status = "Under Review"
            case.save()
            CaseAuditLog.log_action(
                user=request.user,
                case=case,
                action="Directly assigned investigators",
                details=f"Investigators: {[u.username for u in case.assigned_investigators.all()]}",
            )

    case_title = case.get_title()
    case_description = case.get_description()
    case_category = case.get_category()

    media_files = case.evidence.all()

    investigators = User.objects.filter(
        role="investigator", is_active=True, verified=True
    )

    CaseAuditLog.log_action(
        user=request.user, case=case, action=f"Viewed case {case.get_title()}"
    )

    return render(
        request,
        "cases/view_case.html",
        {
            "case": case,
            "title": case_title,
            "category": case_category,
            "media_files": media_files,
            "investigators": investigators,
        },
    )


@login_required
def edit_case(request, case_id):
    case = get_object_or_404(Case, id=case_id)

    if request.user.is_superuser:
        pass
    elif request.user.role == 'regular_user':
        if request.user != case.created_by:
            return HttpResponseForbidden("You can only edit your own cases.")
    elif request.user.role == 'investigator':
        if request.user not in case.assigned_investigators.all():
            return HttpResponseForbidden("You can only edit cases assigned to you.")
    else:
        return HttpResponseForbidden("You do not have permission to edit cases.")

    old_data = {
        "case_title": case.get_title(),
        "case_description": case.get_description(),
        "case_category": case.get_category(),
        "assigned_investigators": list(case.assigned_investigators.all()),
        "case_priority": case.case_priority,
        "case_status": case.case_status,
        "case_status_notes": case.get_status_notes(),
    }

    if request.method == "POST":
        form = EditCaseForm(request.POST, user=request.user, instance=case)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Case updated successfully.")
                for field, old_value in old_data.items():
                    if field == "assigned_investigators":
                        new_value = list(case.assigned_investigators.all())
                        new_value_ids = set(user.id for user in new_value)
                        old_value_ids = set(user.id for user in old_value)
                        if new_value_ids != old_value_ids:
                            CaseAuditLog.log_action(
                                user=request.user,
                                case=case,
                                action=f"Edited {field}",
                                details=f"Old: {', '.join(str(u) for u in old_value)} | New: {', '.join(str(u) for u in new_value)}",
                            )
                    elif field in [
                        "case_title",
                        "case_description",
                        "case_category",
                        "case_status_notes",
                    ]:
                        if field == "case_title":
                            new_value = case.get_title()
                        elif field == "case_description":
                            new_value = case.get_description()
                        elif field == "case_category":
                            new_value = case.get_category()
                        elif field == "case_status_notes":
                            new_value = case.get_status_notes()
                        if old_value != new_value:
                            CaseAuditLog.log_action(
                                user=request.user,
                                case=case,
                                action=f"Edited {field}",
                                details=f"Old: {old_value} | New: {new_value}",
                            )
                    else:
                        new_value = getattr(case, field)
                        if old_value != new_value:
                            CaseAuditLog.log_action(
                                user=request.user,
                                case=case,
                                action=f"Edited {field}",
                                details=f"Old: {old_value} | New: {new_value}",
                            )

                return redirect("cases:view_case", case_id=case.id)
            except Exception as e:
                logger.error(f"Error updating case: {e}")
                messages.error(request, "Failed to update case. Please try again.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = EditCaseForm(
            user=request.user,
            instance=case,
            initial={
                "case_title": case.get_title(),
                "case_description": case.get_description(),
                "case_category": case.get_category(),
                "case_status_notes": case.get_status_notes(),
            },
        )

    template = (
        "cases/edit_case_admin.html"
        if request.user.is_staff
        else "cases/edit_case.html"
    )
    return render(request, template, {"form": form, "case": case})


@login_required
def assign_investigator(request, case_id):
    case = get_object_or_404(Case, id=case_id)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "propose":
            if request.user != case.created_by:
                return HttpResponseForbidden(
                    "Only case creator can propose assignments."
                )
            investigator_ids = request.POST.getlist("investigators")
            notes = request.POST.get("notes", "")
            request_obj = AssignmentRequest.objects.create(
                case=case,
                requested_by=request.user,
                request_type="assignment",
                status="pending_admin",
                notes=notes,
            )
            request_obj.assigned_users.set(investigator_ids)
            case.case_status = "Pending Admin Approval"
            case.save()
            CaseAuditLog.log_action(
                user=request.user,
                case=case,
                action="Proposed investigator assignment",
                details=f"Investigators: {investigator_ids}, Notes: {notes}",
            )
        elif action == "approve":
            if not request.user.is_staff:
                return HttpResponseForbidden("Only admins can approve.")
            request_id = request.POST.get("request_id")
            request_obj = get_object_or_404(AssignmentRequest, id=request_id, case=case)
            if request_obj.status == "pending_admin":
                request_obj.status = "approved"
                request_obj.approved_at = timezone.now()
                request_obj.save()
                case.assigned_investigators.set(request_obj.assigned_users.all())
                case.case_status = "Under Review"
                case.save()
                CaseAuditLog.log_action(
                    user=request.user,
                    case=case,
                    action="Approved investigator assignment",
                    details=f"Investigators: {list(request_obj.assigned_users.values_list('username', flat=True))}",
                )
        elif action == "reject":
            if not request.user.is_staff:
                return HttpResponseForbidden("Only admins can reject.")
            request_id = request.POST.get("request_id")
            request_obj = get_object_or_404(AssignmentRequest, id=request_id, case=case)
            request_obj.status = "rejected"
            request_obj.save()
            case.case_status = "Open"
            case.save()
            CaseAuditLog.log_action(
                user=request.user,
                case=case,
                action="Rejected investigator assignment",
                details=f"Request by {request_obj.requested_by.username}",
            )
        elif action == "assign_direct":
            if not request.user.is_staff:
                return HttpResponseForbidden("Only admins can assign.")
            investigators = request.POST.getlist("direct_investigators")
            case.assigned_investigators.set(investigators)
            case.save()
            CaseAuditLog.log_action(
                user=request.user,
                case=case,
                action="Directly assigned investigators",
                details=f"Investigators: {[u.username for u in case.assigned_investigators.all()]}",
            )
        return redirect("cases:assign_investigators", case_id=case.id)

    users = User.objects.filter(role="investigator", is_active=True, verified=True)
    pending_requests = case.assignment_requests.filter(status__in=["pending_admin"])

    return render(
        request,
        "cases/assign_investigator.html",
        {
            "case": case,
            "users": users,
            "assigned": case.assigned_investigators.all(),
            "pending_requests": pending_requests,
        },
    )


@login_required
def request_case_closure(request, case_id):
    case = get_object_or_404(Case, id=case_id)
    if (
        request.user != case.created_by
        and request.user not in case.assigned_investigators.all()
    ):
        return HttpResponseForbidden("You cannot request closure.")

    if case.closure_requested:
        return HttpResponse("Closure already requested.")

    if request.method == "POST":
        reason = request.POST.get("close_reason")

        case.close_reason = reason
        case.closure_requested = True
        case.case_status = "Under Review"  # moves to review stage
        case.save()

        CaseAuditLog.log_action(
            user=request.user,
            case=case,
            action="Requested case closure",
            details=reason,
        )

        return redirect("view_case", case_id=case.id)

    return render(request, "cases/request_closure.html", {"case": case})


@login_required
def close_case(request, case_id):
    case = get_object_or_404(Case, id=case_id)

    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("you are not autorised to close this case")

    if case.case_status != "Closed":
        return HttpResponseForbidden("Case status must be 'closed' before finalizing.")

    case.case_status = "Closed"
    case.closure_approved = False
    case.save()

    CaseAuditLog.log_action(
        user=request.user,
        case=case,
        action="Closed case -metadata and content are now read only",
    )

    return redirect("cases:view_case", case_id=case.id)


@login_required
def approve_case_closure(request, case_id):
    case = get_object_or_404(Case, id=case_id)
    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden(
            "Only the case creator or admins can approve closures."
        )

    if not case.closure_requested:
        return HttpResponse("No closure request pending.")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "approve":
            if request.user == case.created_by:
                case.closure_creator_approved = True
                CaseAuditLog.log_action(
                    user=request.user, case=case, action="Creator approved case closure"
                )
            elif request.user.is_staff:
                case.closure_approved = True
                CaseAuditLog.log_action(
                    user=request.user, case=case, action="Admin approved case closure"
                )

            if case.closure_creator_approved and case.closure_approved:
                case.case_status = "Closed"
                CaseAuditLog.log_action(
                    user=request.user,
                    case=case,
                    action="Case closed after both approvals",
                )

        elif action == "reject":
            case.closure_requested = False
            case.closure_creator_approved = False
            case.closure_approved = False
            case.case_status = "Under Review"

            CaseAuditLog.log_action(
                user=request.user,
                case=case,
                action="Rejected case closure - reset to pending",
            )

        case.save()
        return redirect("view_case", case_id=case.id)

    return render(request, "cases/approve_closure.html", {"case": case})


@login_required
def archive_case(request, case_id):
    case = get_object_or_404(Case, id=case_id)

    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("You are not authorized to archive this case")

    if case.case_status != "Closed":
        return HttpResponseForbidden("Only closed case can be archived")

    case.case_status = "Archived"
    case.save()

    CaseAuditLog.log_action(
        user=request.user,
        case=case,
        action=f"Archived case {case.get_title()}. Case is now read-only",
    )

    return redirect("cases:view_case", case_id=case.id)


@login_required
def withdraw_case(request, case_id):
    case = get_object_or_404(Case, id=case_id)
    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("You are not authorized to withdraw this case.")
    if case.case_status in ["Closed", "Archived"]:
        return HttpResponseForbidden("Cannot withdraw a closed or archived case.")
    case.case_status = "Withdrawn"
    case.save()
    CaseAuditLog.log_action(
        user=request.user, case=case, action="Withdrawn case - case is now read-only"
    )

    return redirect("cases:view_case", case_id=case.id)


@login_required
def mark_invalid_case(request, case_id):
    case = get_object_or_404(Case, id=case_id)
    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden(
            "You are not authorized to mark this case invalid."
        )
    if case.case_status in ["Closed", "Archived"]:
        return HttpResponseForbidden("Cannot mark a closed or archived case invalid.")
    case.case_status = "Invalid"
    case.save()
    reason = request.POST.get("reason", None)
    if reason:
        CaseAuditLog.log_action(
            user=request.user,
            case=case,
            action="Marked case invalid",
            details=f"Reason: {reason}",
        )
    else:
        CaseAuditLog.log_action(
            user=request.user, case=case, action="Marked case invalid"
        )

    return redirect("cases:view_case", case_id=case.id)


@login_required
def upload_media(request, case_id):
    case = get_object_or_404(Case, id=case_id)
    if request.user != case.created_by or case.assigned_investigators.exists():
        return HttpResponseForbidden(
            "You are not allowed to upload evidence in this case"
        )

    if case.case_status in ["Closed", "Archived", "Invalid"]:
        return HttpResponseForbidden(
            f"Cannot upload media to a {case.case_status} case."
        )

    if request.method == "POST":
        form = CaseMediaForm(request.POST, request.FILES)
        if form.is_valid():
            media = form.save(commit=False)
            media.case = case
            media.save()

            try:
                CaseAuditLog.log_action(
                    user=request.user,
                    case=case,
                    action="Uploaded media",
                    details=f"File: {media.media.name}, Type: {media.media_type}, Description: {media.description}",
                )
            except Exception as e:
                logger.error(f"Failed to log media upload for case {case.id}: {e}")
            return redirect("cases:view_case", case_id=case.id)

    else:
        form = CaseMediaForm()

    return render(request, "cases/upload_media.html", {"form": form, "case": case})


@login_required
def view_media(request, media_id):
    media = get_object_or_404(CaseMedia, id=media_id)
    case = media.case

    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("Your are not authorized to access this evidence")

    decrypted_file = media.download_decrypted()

    try:
        CaseAuditLog.log_action(
            user=request.user,
            case=case,
            action="Viewed media",
            details=f"File: {media.media.name}",
        )
    except Exception as e:
        logger.error(f"Failed to log media view for case {case.id}: {e}")

    response = FileResponse(decrypted_file, content_type="application/octet-stream")
    response["Content-Disposition"] = f'inline; filename="{decrypted_file.name}"'
    return response


@login_required
def edit_media_description(request, media_id):
    media = get_object_or_404(CaseMedia, id=media_id)
    case = media.case

    if case.case_status in ["Closed", "Archived", "Withdrawn", "Invalid"]:
        return HttpResponseForbidden("Cannot edit media in a read-only case.")

    if request.user != case.created_by:
        return HttpResponseForbidden("Not authorized to edit case media")

    old_description = media.description

    if request.method == "POST":
        new_description = request.POST.get("description")
        if new_description:
            media.description = new_description
            media.save()

        CaseAuditLog.log_action(
            user=request.user,
            case=case,
            action="Edited media description",
            details=f"File: {media.media.name}, Old: {old_description} | New: {new_description}",
        )
        return redirect("cases:view_case", case_id=case.id)
    return render(request, "cases/edit_media.html", {"media": media})


@login_required
def mark_media_invalid(request, media_id):
    media = get_object_or_404(CaseMedia, id=media_id)
    case = media.case
    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("Not authorized to mark this media invalid.")
    if case.case_status in ["Closed", "Archived"]:
        return HttpResponseForbidden(
            "Cannot mark media invalid in a closed or archived case."
        )

    media.media_status = "Invalid"
    media.save()

    CaseAuditLog.log_action(
        user=request.user,
        case=case,
        action="Marked media invalid",
        details=f"File: {media.media.name}",
    )

    return redirect("cases:view_case", case_id=case.id)


@login_required
def view_case_audit_log(request, case_id):
    case = get_object_or_404(Case, id=case_id)

    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("Not authorized to view this audit log.")

    media_actions = [
        "Uploaded media",
        "Viewed media",
        "Edited media description",
        "Marked media invalid",
    ]
    audit_logs = case.audit_logs.exclude(action__in=media_actions).order_by(
        "-timestamp"
    )

    return render(
        request,
        "cases/case_audit_log.html",
        {
            "case": case,
            "audit_logs": audit_logs,
        },
    )


@login_required
def download_case_audit_log(request, case_id):
    case = get_object_or_404(Case, id=case_id)

    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("Not authorized to download this audit log.")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="case_{case.id}_audit_log.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(["Timestamp", "User", "Action", "Details"])

    media_actions = [
        "Uploaded media",
        "Viewed media",
        "Edited media description",
        "Marked media invalid",
    ]
    audit_logs = case.audit_logs.exclude(action__in=media_actions).order_by("timestamp")
    for log in audit_logs:
        writer.writerow(
            [
                log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                log.user.username if log.user else "System",
                log.action,
                log.details or "-",
            ]
        )

    return response


@login_required
def view_media_audit_log(request, media_id):
    media = get_object_or_404(CaseMedia, id=media_id)
    case = media.case

    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("Not authorized to view this media audit log.")
    audit_logs = case.audit_logs.filter(
        Q(action__icontains=media.media.name) | Q(details__icontains=media.media.name)
    ).order_by("-timestamp")

    return render(
        request,
        "cases/media_audit_log.html",
        {
            "media": media,
            "case": case,
            "audit_logs": audit_logs,
        },
    )


@login_required
def download_media_audit_log(request, media_id):
    media = get_object_or_404(CaseMedia, id=media_id)
    case = media.case

    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("Not authorized to download this media audit log.")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="media_{media.id}_audit_log.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(["Timestamp", "User", "Action", "Details"])
    audit_logs = case.audit_logs.filter(
        Q(action__icontains=media.media.name) | Q(details__icontains=media.media.name)
    ).order_by("timestamp")

    for log in audit_logs:
        writer.writerow(
            [
                log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                log.user.username if log.user else "System",
                log.action,
                log.details or "-",
            ]
        )

    return response


@login_required
def generate_system_report(request, report_type):
    if not request.user.is_staff:
        return HttpResponseForbidden("Only admins can generate reports.")

    if report_type == "cases_status":
        data = Case.objects.all().values("case_status", "created_by")
    elif report_type == "audit_logs":
        data = CaseAuditLog.objects.all().values(
            "timestamp", "user", "case", "action", "details"
        )
    else:
        return HttpResponse("Unknown report type.")
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{report_type}_report.csv"'

    writer = csv.writer(response)
    writer.writerow(data[0].keys())
    for row in data:
        writer.writerow(row.values())

    return response
