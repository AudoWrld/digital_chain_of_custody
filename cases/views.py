from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseForbidden, FileResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from .models import Case, CaseMedia, EncryptionKey, CaseAuditLog
from .forms import CaseForm, CaseMediaForm,EditCaseForm
import csv
from django.contrib.auth import get_user_model
User = get_user_model()


# list all cases for logged-in user
@login_required
def case_list(request):
    cases = Case.objects.filter(created_by=request.user)
    return render(request, 'cases/case_list.html', {'cases': cases})



@login_required
def create_case(request):
    if request.method == 'POST':
        form = CaseForm(request.POST)
        if form.is_valid():
            title = request.POST.get('title')
            description = request.POST.get('description')
            category = request.POST.get('category')
            
            case = Case(created_by=request.user)
            cipher = Fernet(Fernet.generate_key())
            case.case_title = cipher.encrypt(title.encode())
            case.case_description = cipher.encrypt(description.encode())
            case.case_category = cipher.encrypt(category.encode())
            case.save()
            
            CaseAuditLog.log_action(user=request.user, case=case, action='Created case')
            
            
            EncryptionKey.objects.create(case=case)
            
            return redirect('view_case', case_id=case.id)
    return render(request, 'cases/create_case.html')


@login_required
def view_case(request, case_id):
    case = get_object_or_404(Case, id=case_id)
    
    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("Your are not allowed to view this case!")
    
    case_title = case.get_title()
    case_description = case.get_description()
    case_category = case.get_category() 
    
    media_files = case.evidence.all()
    
    CaseAuditLog.log_action(user=request.user, case=case, action=f"Viewed case {case.case_title}")

    return render(request, 'cases/view_case.html', {
        'case': case,
        'title': case_title,
        'category': case_category,
        'media_files': media_files,
    })
    


@login_required
def edit_case(request, case_id):
    case = get_object_or_404(Case, id=case_id)

    # Permission check: only creator or admin can edit
    if request.user != case.created_by and not request.user.is_superuser:
        return HttpResponseForbidden("Not authorized.")

    # Only allow editing if case is open or under review
    if case.case_status not in ['open', 'under_review']:
        return HttpResponseForbidden("Case cannot be edited in its current status.")

    old_data = {
        'title': case.case_title,
        'description': case.case_description,
        'category': case.case_category,
        'assigned_investigators': list(case.assigned_investigators.all()),
        'priority': case.case_priority,
        'status_notes': case.case_status_notes
    }

    if request.method == 'POST':
        form = EditCaseForm(request.POST, instance=case)
        if form.is_valid():
            form.save()

            # Log changes in audit trail
            for field, old_value in old_data.items():
                new_value = getattr(case, field)
                # Handle ManyToMany field for assigned_investigators
                if field == 'assigned_investigators':
                    new_value_ids = set(user.id for user in new_value)
                    old_value_ids = set(user.id for user in old_value)
                    if new_value_ids != old_value_ids:
                        CaseAuditLog.log_action(
                            user=request.user,
                            case=case,
                            action=f"Edited {field}",
                            details=f"Old: {', '.join(str(u) for u in old_value)} | New: {', '.join(str(u) for u in new_value)}"
                        )
                else:
                    if old_value != new_value:
                        CaseAuditLog.log_action(
                            user=request.user,
                            case=case,
                            action=f"Edited {field}",
                            details=f"Old: {old_value} | New: {new_value}"
                        )

            return redirect('view_case', case_id=case.id)
    else:
        form = EditCaseForm(instance=case)

    return render(request, 'cases/edit_case.html', {'form': form, 'case': case})




@login_required
def assign_investigator(request, case_id):
    case = get_object_or_404(Case, id=case_id)

    # Only staff/admin can assign investigators
    if not request.user.is_staff:
        return HttpResponseForbidden("Not allowed.")

    if request.method == "POST":
        investigator_ids = request.POST.getlist("investigators")
        case.assigned_investigators.set(investigator_ids)
        case.save()

        CaseAuditLog.log_action(
            user=request.user,
            case=case,
            action="Assigned investigators",
            details=f"Investigators: {investigator_ids}"
        )

        return redirect("view_case", case_id=case.id)

    users = User.objects.all()

    return render(request, "cases/assign_investigator.html", {
        "case": case,
        "users": users,
        "assigned": case.assigned_investigators.all(),
    })


@login_required
def request_case_closure(request, case_id):
    case = get_object_or_404(Case, id=case_id)

    # Only creator or investigators can request closure
    if request.user != case.created_by and request.user not in case.assigned_investigators.all():
        return HttpResponseForbidden("You cannot request closure.")

    if case.closure_requested:
        return HttpResponse("Closure already requested.")

    if request.method == "POST":
        reason = request.POST.get("close_reason")

        case.close_reason = reason
        case.closure_requested = True
        case.case_status = "Under Review"   # moves to review stage
        case.save()

        CaseAuditLog.log_action(
            user=request.user,
            case=case,
            action="Requested case closure",
            details=reason
        )

        return redirect("view_case", case_id=case.id)

    return render(request, "cases/request_closure.html", {"case": case})


@login_required
def close_case(request, case_id):
    case = get_object_or_404(Case, id=case_id)
    
    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("you are not autorised to close this case")
    
    if case.case_status != 'Closed':
        return HttpResponseForbidden("Case status must be 'closed' before finalizing.")
    
    case.case_status = 'Closed'
    case.closure_approved = False
    case.save()
    
    CaseAuditLog.log_action(
        user=request.user,
        case=case,
        action='Closed case -metadata and content are now read only'
    )
    
    return redirect('view_case', case_id=case.id)



@login_required
def approve_case_closure(request, case_id):
    case = get_object_or_404(Case, id=case_id)

    if not request.user.is_staff:
        return HttpResponseForbidden("Only admins can approve closures.")

    if not case.closure_requested:
        return HttpResponse("No closure request pending.")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "approve":
            case.case_status = "Closed"
            case.closure_approved = True

            CaseAuditLog.log_action(
                user=request.user,
                case=case,
                action="Approved case closure"
            )

        elif action == "reject":
            case.closure_requested = False
            case.case_status = "In Progress"

            CaseAuditLog.log_action(
                user=request.user,
                case=case,
                action="Rejected case closure"
            )

        case.save()
        return redirect("view_case", case_id=case.id)

    return render(request, "cases/approve_closure.html", {"case": case})



    
@login_required
def archive_case(request, case_id):
    case = get_object_or_404(Case, id=case_id)
    
    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("You are not authorized to archive this case")
    
    if case.case_status != 'Closed':
        return HttpResponseForbidden("Only closed case can be archived")
    
    case.case_status = 'Archived'
    case.save()
    
    CaseAuditLog.log_action(
        user=request.user,
        case=case,
        action=f"Archived case {case.case_title}. Case is now read-only"
    )
    
    return redirect('view_case', case_id=case.id)




@login_required
def withdraw_case(request, case_id):
    case = get_object_or_404(Case, id=case_id)

    # Permission check: creator or staff
    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("You are not authorized to withdraw this case.")

    # Only allow withdrawal if the case is not already Closed or Archived
    if case.case_status in ['Closed', 'Archived']:
        return HttpResponseForbidden("Cannot withdraw a closed or archived case.")

    # Update status to Withdrawn
    case.case_status = 'Withdrawn'
    case.save()

    # Log the action
    CaseAuditLog.log_action(
        user=request.user,
        case=case,
        action="Withdrawn case - case is now read-only"
    )

    return redirect('view_case', case_id=case.id)



@login_required
def mark_invalid_case(request, case_id):
    case = get_object_or_404(Case, id=case_id)

    # Permission check: creator or staff
    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("You are not authorized to mark this case invalid.")

    # Only allow marking invalid if the case is not Closed or Archived
    if case.case_status in ['Closed', 'Archived']:
        return HttpResponseForbidden("Cannot mark a closed or archived case invalid.")

    # Update status to Invalid
    case.case_status = 'Invalid'
    case.save()

    # Optional: store reason for invalidation
    reason = request.POST.get('reason', None)
    if reason:
        CaseAuditLog.log_action(
            user=request.user,
            case=case,
            action="Marked case invalid",
            details=f"Reason: {reason}"
        )
    else:
        CaseAuditLog.log_action(
            user=request.user,
            case=case,
            action="Marked case invalid"
        )

    return redirect('view_case', case_id=case.id)


@login_required
def upload_media(request, case_id):
    case = get_object_or_404(Case, id=case_id, created_by=request.user)
    if request.user != case.created_by:
        return HttpResponseForbidden("You are not allowed to upload evidence in this case")
    
    if case.case_status in ['Closed', 'Archived','Invalid']:
        return HttpResponseForbidden(f"Cannot upload media to a {case.case_status} case.")

    if request.method == 'POST':
        form = CaseMediaForm(request.POST, request.FILES)
        if form.is_valid():
            media_file = request.FILES.get('media')
            description = request.POST.get('description')
            media_type = request.POST.get('media_type')
            
            
            new_media = CaseMedia(
                case=case,
                media=media_file,
                description=description,
                media_type=media_type
            )
            new_media.save()
            
            CaseAuditLog.log_action(
                user=request.user,
                case=case,
                action=f'Media: {media_file.name} Type: {media_type}'
            )
            return redirect('view_case', case_id=case.id)
        
        return render(request, 'cases/upload_media.html', {'case':case})
    
    
@login_required
def view_media(request, media_id):
    media = get_object_or_404(CaseMedia, id=media_id)
    case = media.case
    
    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("Your are not authorized to access this evidence")
    
    decrypted_file = media.download_decrypted()
    
    CaseAuditLog.log_action(user=request.user,case=case, action=f'Media: {media.media.name}')
    
    response = FileResponse(
        decrypted_file,
        content_type='application/octet-stream'
    )
    response['Content-Disposition'] = f'inline; filename="{decrypted_file.name}"'
    return response




@login_required
def edit_media_description(request, media_id):
    media = get_object_or_404(CaseMedia, id=media_id)
    case = media.case
    
    if case.case_status in ['Closed', 'Archived', 'Withdrawn', 'Invalid']:
        return HttpResponseForbidden("Cannot edit media in a read-only case.")
    
    if request.user != case.created_by:
        return HttpResponseForbidden("Not authorized to edit case media")
    
    old_description = media.description
    
    if request.method == 'POST':
        new_description = request.POST.get('description')
        if new_description:
            media.description = new_description
            media.save()
            
            
        CaseAuditLog.log_action(
            user=request.user,
            case=case,
            action="edit media description",
            details=f'Old: {old_description} | New: {new_description}'
        )
        return redirect('view_case', case_id=case.id)
    return render(request, 'cases/edit_media.html', {'media': media})



@login_required
def mark_media_invalid(request, media_id):
    media = get_object_or_404(CaseMedia, id=media_id)
    case = media.case

    # Permission check
    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("Not authorized to mark this media invalid.")

    # Prevent invalidation if case is read-only
    if case.case_status in ['Closed', 'Archived']:
        return HttpResponseForbidden("Cannot mark media invalid in a closed or archived case.")

    # Mark the media as invalid
    media.media_status = 'Invalid'  # <-- You’ll need to add media_status field in CaseMedia model
    media.save()

    # Log the action
    CaseAuditLog.log_action(
        user=request.user,
        case=case,
        action='Marked media invalid',
        details=f'Media: {media.media.name}'
    )

    return redirect('view_case', case_id=case.id)



@login_required
def view_case_audit_log(request, case_id):
    case = get_object_or_404(Case, id=case_id)

    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("Not authorized to view this audit log.")

    audit_logs = case.audit_logs.all().order_by('-timestamp')

    return render(request, 'cases/case_audit_log.html', {
        'case': case,
        'audit_logs': audit_logs,
    })
    
    


@login_required
def download_case_audit_log(request, case_id):
    case = get_object_or_404(Case, id=case_id)

    # Permission check: only creator or staff
    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("Not authorized to download this audit log.")

    # Prepare HTTP response for CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="case_{case.id}_audit_log.csv"'

    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'User', 'Action', 'Details'])

    # Fetch all audit logs ordered by timestamp
    audit_logs = case.audit_logs.all().order_by('timestamp')
    for log in audit_logs:
        writer.writerow([
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            log.user.username if log.user else "System",
            log.action,
            log.details or "-"
        ])

    return response


@login_required
def view_media_audit_log(request, media_id):
    media = get_object_or_404(CaseMedia, id=media_id)
    case = media.case

    # Permission check: only creator or staff can view audit logs
    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("Not authorized to view this media audit log.")

    # Fetch all audit logs for this case that relate to this media
    audit_logs = case.audit_logs.filter(details__icontains=media.media.name).order_by('-timestamp')

    return render(request, 'cases/media_audit_log.html', {
        'media': media,
        'case': case,
        'audit_logs': audit_logs,
    })



@login_required
def download_media_audit_log(request, media_id):
    media = get_object_or_404(CaseMedia, id=media_id)
    case = media.case

    # Permission check: only creator or staff
    if request.user != case.created_by and not request.user.is_staff:
        return HttpResponseForbidden("Not authorized to download this media audit log.")

    # Prepare HTTP response for CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="media_{media.id}_audit_log.csv"'

    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'User', 'Action', 'Details'])

    # Filter audit logs related to this media
    audit_logs = case.audit_logs.filter(details__icontains=media.media.name).order_by('timestamp')

    for log in audit_logs:
        writer.writerow([
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            log.user.username if log.user else "System",
            log.action,
            log.details or "-"
        ])

    return response


# report view
@login_required
def generate_system_report(request, report_type):
    if not request.user.is_staff:
        return HttpResponseForbidden("Only admins can generate reports.")

    if report_type == 'cases_status':
        data = Case.objects.all().values('case_status', 'created_by')
    elif report_type == 'audit_logs':
        data = CaseAuditLog.objects.all().values('timestamp', 'user', 'case', 'action', 'details')
    else:
        return HttpResponse("Unknown report type.")

    # Convert to CSV for download
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_report.csv"'

    writer = csv.writer(response)
    writer.writerow(data[0].keys())
    for row in data:
        writer.writerow(row.values())

    return response
