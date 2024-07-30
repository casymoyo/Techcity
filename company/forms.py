from django import forms
from .models import Branch, Company

class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = '__all__'


class CompanyRegistrationForm(forms.ModelForm):

    class Meta:
        model = Company
        fields = '__all__'
