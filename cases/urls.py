from django.urls import path
from . import views


urlpatterns = [
    path('', views.case_list, name='case_list'),
    path('create/', views.create_case, name='create_case'),
    path('<int:case_id>/', views.view_case, name='view_case'),
    path('<int:case_id>/edit/', views.edit_case, name='edit_case'),
    
    
    # case actions
    
path('<int:case_id>/archive/', views.archive_case, name='archive_case'),
path('<int:case_id>/request-close/', views.request_case_closure, name='request_case_closure'),
path('<int:case_id>/withdraw/', views.withdraw_case, name='withdraw_case'),
path('<int:case_id>/invalidate/', views.mark_invalid_case, name='invalidate_case'),


# admin approval action
path('<int:case_id>/approve-closure/', views.approve_case_closure, name='admin_approve_case_closure'),

# assign investigators
path('<int:case_id>/assign/', views.assign_investigator, name='assign_investigators'),

# --- AUDIT LOGS ---
path('<int:case_id>/audit/', views.view_case_audit_log, name='view_case_audit_log'),


# --- MEDIA ---
path('<int:case_id>/upload-media/', views.upload_media, name='upload_media'),
path('media/<int:media_id>/', views.view_media, name='view_media'),

path('media/<int:media_id>/edit-description/', views.edit_media_description, name='edit_media_description'),
path('media/<int:media_id>/invalidate/', views.mark_media_invalid, name='mark_media_invalid'),

# media audit log
path('media/<int:media_id>/audit/', views.view_media_audit_log, name='view_media_audit_log'),

# decrypted media download


]
