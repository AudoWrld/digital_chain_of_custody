from django import forms
from .models import Evidence


class EvidenceUploadForm(forms.ModelForm):
    class Meta:
        model = Evidence
        fields = ['media', 'description']
        widgets = {
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter evidence description'
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
    
    def clean_media(self):
        media = self.cleaned_data.get('media')
        if media:
            if media.size > 50 * 1024 * 1024:
                raise forms.ValidationError('File size cannot exceed 50MB')
            self.cleaned_data['original_filename'] = media.name
        return media
    
    def clean(self):
        cleaned_data = super().clean()
        media = cleaned_data.get('media')
        
        if media:
            media_type = self._detect_media_type(media)
            cleaned_data['media_type'] = media_type
        
        return cleaned_data
    
    def _detect_media_type(self, media):
        file_type = media.content_type.lower()
        filename = media.name.lower()
        
        if file_type.startswith('image/'):
            return 'image'
        elif file_type.startswith('video/'):
            return 'video'
        elif file_type.startswith('audio/'):
            return 'audio'
        elif 'pdf' in file_type or filename.endswith('.pdf'):
            return 'document'
        elif filename.endswith(('.doc', '.docx')):
            return 'document'
        elif filename.endswith('.txt'):
            return 'document'
        else:
            return 'other'