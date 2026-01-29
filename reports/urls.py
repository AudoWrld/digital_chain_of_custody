from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('create/<str:case_id>/', views.create_analysis_report, name='create'),
    path('create/<str:case_id>/<int:evidence_id>/', views.create_analysis_report, name='create_for_evidence'),
    path('view/<int:report_id>/', views.view_analysis_report, name='view'),
    path('edit/<int:report_id>/', views.edit_analysis_report, name='edit'),
    path('submit/<int:report_id>/', views.submit_analysis_report, name='submit'),
    path('review/<int:report_id>/', views.review_analysis_report, name='review'),
    path('case/<str:case_id>/', views.case_reports_list, name='case_reports'),
    path('evidence/<int:evidence_id>/', views.evidence_reports_list, name='evidence_reports'),
]
