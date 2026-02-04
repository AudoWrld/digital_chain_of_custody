from django.urls import path
from . import views

app_name = "custody"

urlpatterns = [
    path('dashboard/', views.custody_dashboard, name='dashboard'),
    path('transfer/request/<int:evidence_id>/', views.request_custody_transfer, name='request_transfer'),
    path('transfer/approve/<int:transfer_id>/', views.approve_custody_transfer, name='approve_transfer'),
    path('case-storages/', views.case_storages_list, name='case_storages'),
    path('case-storages/<str:case_id>/', views.view_case_storage, name='view_case_storage'),
    path('log/evidence/<int:evidence_id>/', views.evidence_custody_log, name='evidence_custody_log'),
    path('log/case/<str:case_id>/', views.case_custody_log, name='case_custody_log'),
]
