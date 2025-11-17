from .models import Case, CaseMedia
from django import forms
from django.contrib.auth import get_user_model
User = get_user_model()





# ------------------------------
# Case Creation Form
# ------------------------------
class CaseForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = ['case_title', 'case_description', 'case_category', 'case_priority']

    case_title = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="Case Title"
    )
    case_description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control'}),
        label="Description"
    )
    case_category = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="Case Category"
    )
    case_priority = forms.ChoiceField(
        choices=Case.PRIORITY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Priority"
    )

    def save(self, commit=True):
        """
        Prevent Django from trying to encrypt twice.
        Your Case model handles encryption in save().
        """
        case = super().save(commit=False)

        if commit:
            case.save()
        return case


# ------------------------------
# Edit Case Form
# ------------------------------
class EditCaseForm(forms.ModelForm):

    assigned_investigators = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        required=False,
        label="Assign Investigators"
    )

    class Meta:
        model = Case
        fields = [
            'case_priority',
            'assigned_investigators',
            'case_status',
            'case_status_notes',
        ]

        widgets = {
            'case_priority': forms.Select(attrs={'class': 'form-select'}),
            'case_status': forms.Select(attrs={'class': 'form-select'}),
            'case_status_notes': forms.Textarea(attrs={'class': 'form-control'}),
        }

    # Notes and status are encrypted BinaryFields — your model automatically encrypts them.


# ------------------------------
# Case Media Upload Form
# ------------------------------
class CaseMediaForm(forms.ModelForm):
    description_text = forms.CharField(max_length=255)

    class Meta:
        model = CaseMedia
        fields = ["media", "media_type"]

    def save(self, commit=True):
        media = super().save(commit=False)
        media.description = self.cleaned_data["description_text"]

        if commit:
            media.save()
        return media

class AssignInvestigatorForm(forms.ModelForm):
    assigned_investigators = forms.ModelMultipleChoiceField(
        queryset=None,
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Case
        fields = ["assigned_investigators"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth.models import User
        self.fields["assigned_investigators"].queryset = User.objects.all()
