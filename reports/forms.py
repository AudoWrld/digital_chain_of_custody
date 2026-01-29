from django import forms
from .models import AnalysisReport
from cases.models import Case
from evidence.models import Evidence


class AnalysisReportForm(forms.ModelForm):
    class Meta:
        model = AnalysisReport
        fields = ['title', 'content', 'findings', 'recommendations']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'create-case-form-input',
                'placeholder': 'Enter report title'
            }),
            'content': forms.Textarea(attrs={
                'class': 'create-case-form-textarea',
                'placeholder': 'Enter detailed analysis content',
                'rows': 10
            }),
            'findings': forms.Textarea(attrs={
                'class': 'create-case-form-textarea',
                'placeholder': 'Enter key findings',
                'rows': 5
            }),
            'recommendations': forms.Textarea(attrs={
                'class': 'create-case-form-textarea',
                'placeholder': 'Enter recommendations',
                'rows': 5
            }),
        }


class AnalysisReportCreateForm(AnalysisReportForm):
    def __init__(self, *args, **kwargs):
        case = kwargs.pop('case', None)
        evidence = kwargs.pop('evidence', None)
        super().__init__(*args, **kwargs)
        self.case = case
        self.evidence = evidence


class AnalysisReportReviewForm(forms.ModelForm):
    class Meta:
        model = AnalysisReport
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'create-case-form-input'
            })
        }