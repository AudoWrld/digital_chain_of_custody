from django.utils import timezone
from datetime import timedelta
from .models import Case


class CaseStatusMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self.update_case_status()
        response = self.get_response(request)
        return response

    def update_case_status(self):
        one_hour_ago = timezone.now() - timedelta(hours=1)
        Case.objects.filter(
            case_status='Open',
            date_created__lte=one_hour_ago
        ).update(case_status='Pending Admin Approval')