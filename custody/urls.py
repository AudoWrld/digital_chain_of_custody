from django.urls import path
from . import views

app_name = "custody"

urlpatterns = [
    path('dashboard/', views.custody_dashboard, name='dashboard'),
    path('transfer/request/<int:evidence_id>/', views.request_custody_transfer, name='request_transfer'),
    path('transfer/approve/<int:transfer_id>/', views.approve_custody_transfer, name='approve_transfer'),
    path('storage/', views.storage_locations_list, name='storage_locations'),
    path('storage/create/', views.create_storage_location, name='create_storage_location'),
    path('storage/edit/<int:location_id>/', views.edit_storage_location, name='edit_storage_location'),
    path('storage/assign/<int:evidence_id>/', views.assign_evidence_storage, name='assign_storage'),
    path('log/evidence/<int:evidence_id>/', views.evidence_custody_log, name='evidence_custody_log'),
    path('log/case/<str:case_id>/', views.case_custody_log, name='case_custody_log'),
]
