from .models import Case
from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class CaseForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = ["case_title", "case_description", "case_category", "case_priority"]

    case_title = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "required": "required",
                "autocomplete": "off",
            }
        ),
        label="Case Title",
        required=True,
    )

    case_description = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": "4"}),
        label="Description",
        required=True,
        min_length=150,
    )
    case_category = forms.ChoiceField(
        choices=Case.CASE_CATEGORIES,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Case Category",
    )
    case_priority = forms.ChoiceField(
        choices=Case.PRIORITY_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Priority",
    )

    def clean_case_description(self):
        description = self.cleaned_data.get("case_description")
        if len(description) < 150:
            raise forms.ValidationError("Description must be at least 150 characters.")
        return description

    def save(self, commit=True):
        case = super().save(commit=False)

        if commit:
            case.save()
        return case


class EditCaseForm(forms.ModelForm):

    case_title = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "required": "required",
                "autocomplete": "off",
            }
        ),
        label="Case Title",
        required=True,
    )

    case_description = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": "4"}),
        label="Description",
        required=True,
        min_length=150,
    )

    case_category = forms.ChoiceField(
        choices=Case.CASE_CATEGORIES,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Case Category",
    )

    case_priority = forms.ChoiceField(
        choices=Case.PRIORITY_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Priority",
    )

    assigned_investigators = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(
            role="investigator", is_active=True, verified=True
        ),
        widget=forms.SelectMultiple(attrs={"class": "form-select"}),
        required=False,
        label="Assign Investigators",
    )

    class Meta:
        model = Case
        fields = [
            "case_title",
            "case_description",
            "case_category",
            "case_priority",
            "assigned_investigators",
            "case_status",
            "case_status_notes",
        ]

        widgets = {
            "case_status": forms.Select(attrs={"class": "form-select"}),
            "case_status_notes": forms.Textarea(attrs={"class": "form-control"}),
        }

    def clean_case_description(self):
        description = self.cleaned_data.get("case_description")
        if len(description) < 150:
            raise forms.ValidationError("Description must be at least 150 characters.")
        return description

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user and not user.is_staff:
            fields_to_remove = [
                "assigned_investigators",
                "case_status",
                "case_status_notes",
            ]
            for field in fields_to_remove:
                self.fields.pop(field, None)


class AssignInvestigatorForm(forms.ModelForm):
    assigned_investigators = forms.ModelMultipleChoiceField(
        queryset=None, widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Case
        fields = ["assigned_investigators"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth.models import User

        self.fields["assigned_investigators"].queryset = User.objects.filter(
            role="investigator", is_active=True, verified=True
        )
