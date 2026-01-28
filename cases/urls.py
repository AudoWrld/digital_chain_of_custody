from django.urls import path
from . import views

app_name = "cases"

urlpatterns = [
    path("", views.case_list, name="case_list"),
    path("assigned/", views.assigned_cases, name="assigned_cases"),
    path("create/", views.create_case, name="create_case"),
    path("<str:case_id>/", views.view_case, name="view_case"),
    path("<str:case_id>/edit/", views.edit_case, name="edit_case"),
    # case actions
    path("<str:case_id>/close/", views.close_case, name="close_case"),
    path("<str:case_id>/archive/", views.archive_case, name="archive_case"),
    path(
        "<str:case_id>/request-close/",
        views.request_case_closure,
        name="request_case_closure",
    ),
    path("<str:case_id>/withdraw/", views.withdraw_case, name="withdraw_case"),
    path("<str:case_id>/invalidate/", views.mark_invalid_case, name="invalidate_case"),
    # admin approval action
    path(
        "<str:case_id>/approve-closure/",
        views.approve_case_closure,
        name="admin_approve_case_closure",
    ),
    # assign investigators
    path(
        "<str:case_id>/assign/", views.assign_investigator, name="assign_investigators"
    ),
    # investigator actions
    path(
        "<str:case_id>/accept/", views.accept_case, name="accept_case"
    ),
    path(
        "<str:case_id>/under-review/", views.mark_under_review, name="mark_under_review"
    ),
    # --- AUDIT LOGS ---
    path("<str:case_id>/audit/", views.view_case_audit_log, name="view_case_audit_log"),
]
