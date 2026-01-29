from functools import wraps
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required


def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            if request.user.role not in allowed_roles:
                return HttpResponseForbidden("You do not have permission to access this page.")
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def regular_user_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.role != 'regular_user':
            return HttpResponseForbidden("Only regular users can access this page.")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def investigator_or_regular_user_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if request.user.role not in ['regular_user', 'investigator']:
            return HttpResponseForbidden("You do not have permission to access this page.")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def investigator_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if request.user.role != 'investigator':
            return HttpResponseForbidden("Only investigators can access this page.")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def analyst_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if request.user.role != 'analyst':
            return HttpResponseForbidden("Only analysts can access this page.")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if request.user.role != 'admin':
            return HttpResponseForbidden("Only admins can access this page.")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def auditor_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if request.user.role != 'auditor':
            return HttpResponseForbidden("Only auditors can access this page.")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def custodian_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if request.user.role != 'custodian':
            return HttpResponseForbidden("Only custodians can access this page.")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def can_upload_evidence(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if request.user.role not in ['investigator', 'admin']:
            return HttpResponseForbidden("Only investigators and admins can upload evidence.")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def can_modify_custody(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if request.user.role not in ['investigator', 'custodian', 'admin']:
            return HttpResponseForbidden("Only investigators, custodians, and admins can modify custody records.")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def can_create_case(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if request.user.role not in ['regular_user', 'admin']:
            return HttpResponseForbidden("Only regular users and admins can create cases.")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def can_close_case(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if request.user.role not in ['admin']:
            return HttpResponseForbidden("Only admins can close cases.")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view
