from django import forms
from .models import User

class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput,
        label="Password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput,
        label="Confirm Password"
    )
    
    # Explicitly define role field to exclude admin/superuser
    role = forms.ChoiceField(
        choices=[],
        label="Role",
        help_text="Select your role"
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "role", "password"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set role choices excluding admin/superuser
        self.fields['role'].choices = [
            ('regular_user', 'Regular User'),
            ('investigator', 'Investigator'),
            ('analyst', 'Analyst'),
            ('custodian', 'Custodian'),
            ('auditor', 'Auditor'),
        ]
        # Set default role
        if not self.initial.get('role'):
            self.fields['role'].initial = 'regular_user'

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email.split("@")[0]
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user

