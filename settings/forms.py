# forms.py
from django import forms

class EmailSettingsForm(forms.Form):
    EMAIL_HOST = forms.CharField(label='SMTP Host')
    EMAIL_PORT = forms.IntegerField(label='SMTP Port')
    EMAIL_USE_TLS = forms.BooleanField(label='Use TLS', required=False)
    EMAIL_HOST_USER = forms.EmailField(label='Email Address')
    EMAIL_HOST_PASSWORD = forms.CharField(
        label='Email Password', widget=forms.PasswordInput()
    )
