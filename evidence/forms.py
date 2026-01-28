from django import forms
from .models import Evidence


class EvidenceUploadForm(forms.ModelForm):
    class Meta:
        model = Evidence
        fields = ['media', 'description', 'media_type']
        widgets = {
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter evidence description'
            }),
            'media_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'media': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*,video/*,audio/*,.pdf,.doc,.docx,.txt'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['media'].required = True
        self.fields['description'].required = True
        self.fields['media_type'].required = True
    
    def clean_media(self):
        media = self.cleaned_data.get('media')
        if media:
            if media.size > 50 * 1024 * 1024:
                raise forms.ValidationError('File size cannot exceed 50MB')
            self.cleaned_data['original_filename'] = media.name
        return media