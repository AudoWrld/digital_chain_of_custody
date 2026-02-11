from django.urls import path
from . import views

app_name = "auditor"

urlpatterns = [
    path("", views.auditor_dashboard, name="dashboard"),
    path("audit-logs/", views.audit_logs, name="audit_logs"),
    path("case/<str:case_id>/audit/", views.case_audit_logs, name="auditor_case_audit_logs"),
    path("chain-of-custody/", views.chain_of_custody_report, name="chain_of_custody"),
    path("integrity-check/", views.evidence_integrity_check, name="integrity_check"),
    path("evidence/<int:evidence_id>/custody/", views.evidence_custody_history, name="evidence_custody_history"),
    path("case/<str:case_id>/integrity/", views.case_integrity_report, name="case_integrity_report"),
]
