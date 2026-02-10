from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseForbidden, FileResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from .models import Case, CaseAuditLog, AssignmentRequest, InvestigatorCaseStatus
from evidence.models import Evidence
from .forms import CaseForm, EditCaseForm
from .permissions import regular_user_required, role_required, can_create_case, can_close_case
import csv
from django.contrib.auth import get_user_model
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@login_required
def case_list(request):
    if request.user.is_superuser:
        cases = Case.objects.all().select_related("encryption_key").order_by('-date_created')
        is_superuser = True
    elif request.user.role == "regular_user":
        cases = Case.objects.filter(created_by=request.user).select_related(
            "encryption_key"
        ).order_by('-date_created')
        is_superuser = False
    elif request.user.role == "investigator":
        cases = Case.objects.filter(assigned_investigators=request.user).select_related(
            "encryption_key"
        ).order_by('-date_created')
        is_superuser = False
    else:
        return HttpResponseForbidden("You do not have permission to view cases.")

    return render(
        request, "cases/case_list.html", {"cases": cases, "is_superuser": is_superuser}
    )


@login_required
def assigned_cases(request):
    if request.user.is_superuser:
        cases = Case.objects.all().select_related("encryption_key").order_by('-date_created')
        is_superuser = True
    elif request.user.role == "investigator":
        cases = Case.objects.filter(assigned_investigators=request.user).select_related(
            "encryption_key"
        ).order_by('-date_created')
        is_superuser = False
    else:
        return HttpResponseForbidden("Only investigators can view assigned cases.")

    return render(
        request,
        "cases/assigned_cases.html",
        {"cases": cases, "is_superuser": is_superuser},
    )


@can_create_case
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
                return redirect("cases:view_case", case_id=case.case_id)
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
    case = get_object_or_404(Case, case_id=case_id)

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

    investigator_status = None
    if request.user.role == 'investigator' and request.user in case.assigned_investigators.all():
        investigator_status = InvestigatorCaseStatus.objects.filter(
            case=case,
            investigator=request.user
        ).first()

    investigator_statuses = InvestigatorCaseStatus.objects.filter(case=case)
    investigator_status_dict = {status.investigator.id: status for status in investigator_statuses}

    return render(
        request,
        "cases/view_case.html",
        {
            "case": case,
            "title": case_title,
            "category": case_category,
            "media_files": media_files,
            "investigators": investigators,
            "is_superuser": request.user.is_superuser,
            "investigator_status": investigator_status,
            "investigator_statuses": investigator_status_dict,
        },
    )


@login_required
def edit_case(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)

    if request.user.is_superuser:
        pass
    elif request.user.role == "regular_user":
        if request.user != case.created_by:
            return HttpResponseForbidden("You can only edit your own cases.")
        if case.case_status == "Pending Admin Approval":
            return HttpResponseForbidden("Cannot edit case while pending admin approval.")
    elif request.user.role == "investigator":
        if request.user not in case.assigned_investigators.all():
            return HttpResponseForbidden("You can only edit cases assigned to you.")
        if case.case_status == "Pending Admin Approval":
            return HttpResponseForbidden("Cannot edit case while pending admin approval.")
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

                return redirect("cases:view_case", case_id=case.case_id)
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
    case = get_object_or_404(Case, case_id=case_id)

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
                case.case_status = "Approved & Assigned"
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
            if case.case_status == "Open":
                case.case_status = "Approved & Assigned"
            case.save()
            CaseAuditLog.log_action(
                user=request.user,
                case=case,
                action="Directly assigned investigators",
                details=f"Investigators: {[u.username for u in case.assigned_investigators.all()]}",
            )
        elif action == "remove_investigator":
            if not request.user.is_staff:
                return HttpResponseForbidden("Only admins can remove investigators.")
            investigator_id = request.POST.get("investigator_id")
            try:
                investigator = User.objects.get(id=investigator_id)
                case.assigned_investigators.remove(investigator)
                CaseAuditLog.log_action(
                    user=request.user,
                    case=case,
                    action="Removed investigator",
                    details=f"Investigator: {investigator.username}",
                )
            except User.DoesNotExist:
                pass
        return redirect("cases:assign_investigators", case_id=case.case_id)

    users = User.objects.filter(role="investigator", is_active=True, verified=True).exclude(id__in=case.assigned_investigators.all())
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
    case = get_object_or_404(Case, case_id=case_id)
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
        case.case_status = "Under Review"  # Pending admin approval
        case.save()

        CaseAuditLog.log_action(
            user=request.user,
            case=case,
            action="Requested case closure",
            details=reason,
        )

        return redirect("cases:view_case", case_id=case.case_id)

    return render(request, "cases/request_closure.html", {"case": case})


@login_required
@can_close_case
def close_case(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)

    if not (request.user.is_staff or request.user.is_superuser or request.user.role == 'admin'):
        return HttpResponseForbidden("Only admins can close cases.")

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

    return redirect("cases:view_case", case_id=case.case_id)


@login_required
def approve_case_closure(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)
    if not (request.user.is_staff or request.user.is_superuser or request.user.role == 'admin'):
        return HttpResponseForbidden(
            "Only admins can approve closures."
        )

    if not case.closure_requested:
        return HttpResponse("No closure request pending.")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "approve":
            case.case_status = "Closed"
            case.closure_approved = True
            case.save()
            CaseAuditLog.log_action(
                user=request.user,
                case=case,
                action="Admin approved case closure",
                details=f"Closure reason: {case.close_reason}",
            )
        elif action == "reject":
            case.closure_requested = False
            case.case_status = "Under Review"
            case.closure_approved = False
            case.close_reason = ""
            case.save()
            CaseAuditLog.log_action(
                user=request.user,
                case=case,
                action="Admin rejected case closure - reopened case",
            )

        return redirect("cases:view_case", case_id=case.case_id)

    return render(request, "cases/approve_closure.html", {"case": case})


@login_required
def reopen_case(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)
    if not (request.user.is_staff or request.user.is_superuser or request.user.role == 'admin'):
        return HttpResponseForbidden(
            "Only admins can reopen cases."
        )

    if case.case_status != "Closed":
        return HttpResponse("Only closed cases can be reopened.")

    case.case_status = "Under Review"
    case.closure_requested = False
    case.closure_approved = False
    case.save()

    CaseAuditLog.log_action(
        user=request.user,
        case=case,
        action="Admin reopened closed case",
    )

    messages.success(request, "Case has been reopened.")
    return redirect("cases:view_case", case_id=case.case_id)


@login_required
def archive_case(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)

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

    return redirect("cases:view_case", case_id=case.case_id)


@login_required
def withdraw_case(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)
    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("You are not authorized to withdraw this case.")
    if case.case_status in ["Closed", "Archived"]:
        return HttpResponseForbidden("Cannot withdraw a closed or archived case.")
    case.case_status = "Withdrawn"
    case.save()
    CaseAuditLog.log_action(
        user=request.user, case=case, action="Withdrawn case - case is now read-only"
    )

    return redirect("cases:view_case", case_id=case.case_id)


@login_required
def mark_invalid_case(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)
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

    return redirect("cases:view_case", case_id=case.case_id)


@login_required
def view_case_audit_log(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)

    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("Not authorized to view this audit log.")

    audit_logs = case.audit_logs.order_by("-timestamp")

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
    case = get_object_or_404(Case, case_id=case_id)

    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("Not authorized to download this audit log.")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="case_{case.case_id}_audit_log.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(["Timestamp", "User", "Action", "Details"])

    audit_logs = case.audit_logs.order_by("timestamp")
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


@login_required
def accept_case(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)
    
    if request.user.role != 'investigator':
        return HttpResponseForbidden("Only investigators can accept cases")
    
    if request.user not in case.assigned_investigators.all():
        return HttpResponseForbidden("You are not assigned to this case")
    
    investigator_status, created = InvestigatorCaseStatus.objects.get_or_create(
        case=case,
        investigator=request.user
    )
    
    if investigator_status.accepted:
        messages.warning(request, "You have already accepted this case")
        return redirect("cases:view_case", case_id=case.case_id)
    
    investigator_status.accepted = True
    investigator_status.accepted_at = timezone.now()
    investigator_status.save()
    
    CaseAuditLog.log_action(
        user=request.user,
        case=case,
        action="Accepted case assignment"
    )
    
    messages.success(request, "You have accepted this case")
    return redirect("cases:view_case", case_id=case.case_id)


@login_required
def mark_under_review(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)
    
    if request.user.role != 'investigator':
        return HttpResponseForbidden("Only investigators can mark cases as under review")
    
    if request.user not in case.assigned_investigators.all():
        return HttpResponseForbidden("You are not assigned to this case")
    
    investigator_status = get_object_or_404(
        InvestigatorCaseStatus,
        case=case,
        investigator=request.user
    )
    
    if not investigator_status.accepted:
        messages.warning(request, "You must accept the case first")
        return redirect("cases:view_case", case_id=case.case_id)
    
    if investigator_status.under_review:
        messages.warning(request, "You have already marked this case as under review")
        return redirect("cases:view_case", case_id=case.case_id)
    
    investigator_status.under_review = True
    investigator_status.under_review_at = timezone.now()
    investigator_status.save()
    
    case.case_status = "Under Review"
    case.save()
    
    CaseAuditLog.log_action(
        user=request.user,
        case=case,
        action="Marked case as under review"
    )
    
    messages.success(request, "Case marked as under review")
    return redirect("cases:view_case", case_id=case.case_id)
