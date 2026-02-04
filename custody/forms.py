from django import forms
from django.contrib.auth import get_user_model
from .models import CustodyTransfer, StorageLocation, EvidenceStorage

User = get_user_model()


class CustodyTransferRequestForm(forms.ModelForm):
    class Meta:
        model = CustodyTransfer
        fields = ['to_user', 'reason']
        widgets = {
            'to_user': forms.Select(attrs={'class': 'form-control'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        self.evidence = kwargs.pop('evidence', None)
        self.from_user = kwargs.pop('from_user', None)
        super().__init__(*args, **kwargs)
        
        if self.evidence:
            self.fields['to_user'].queryset = User.objects.filter(
                role__in=['investigator', 'analyst', 'custodian', 'admin']
            ).exclude(id=self.from_user.id if self.from_user else None)
        else:
            self.fields['to_user'].queryset = User.objects.filter(
                role__in=['investigator', 'analyst', 'custodian', 'admin']
            )


class CustodyTransferApprovalForm(forms.ModelForm):
    class Meta:
        model = CustodyTransfer
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
        }


class StorageLocationForm(forms.ModelForm):
    class Meta:
        model = StorageLocation
        fields = ['name', 'location_type', 'capacity', 'is_active', 'managed_by']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'location_type': forms.Select(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Capacity in bytes'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'managed_by': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['managed_by'].queryset = User.objects.filter(
            role__in=['custodian', 'admin']
        )


class EvidenceStorageForm(forms.ModelForm):
    class Meta:
        model = EvidenceStorage
        fields = ['storage_location']
        widgets = {
            'storage_location': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['storage_location'].queryset = StorageLocation.objects.filter(is_active=True)