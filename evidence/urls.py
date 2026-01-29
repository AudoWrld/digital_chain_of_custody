from django.urls import path
from . import views

app_name = "evidence"

urlpatterns = [
    path('upload/<str:case_id>/', views.upload_evidence, name='upload'),
    path('view/<int:evidence_id>/', views.view_evidence, name='view'),
    path('file/<int:evidence_id>/', views.view_evidence_file, name='view_file'),
    path('download/<int:evidence_id>/', views.download_evidence_file, name='download_file'),
    path('audit/<int:evidence_id>/', views.audit_evidence, name='audit'),
    path('analyze/<int:evidence_id>/', views.analyze_evidence, name='analyze'),
    path('verify/<int:evidence_id>/', views.verify_evidence_integrity, name='verify'),
    path('api/metadata/<int:evidence_id>/', views.evidence_metadata_api, name='metadata_api'),
    path('api/case/<str:case_id>/', views.case_evidence_list_api, name='case_list_api'),
]
