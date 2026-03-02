from django import forms
from .models import Notice


class NoticeForm(forms.ModelForm):
    class Meta:
        model = Notice
        fields = ['title', 'content', 'is_pinned', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control toss-input',
                'placeholder': '공지사항 제목',
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control toss-input',
                'rows': 8,
                'placeholder': '공지사항 내용을 입력하세요',
            }),
            'is_pinned': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
