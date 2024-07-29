from django import forms
from loguru import logger

from company.models import Company, Branch
from users.models import User
from django.contrib.auth.forms import UserCreationForm


class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    company = forms.ModelChoiceField(queryset=Company.objects.all(), required=True)
    branch = forms.ModelChoiceField(queryset=Branch.objects.none(), required=True)

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'username',
            'email',
            'phonenumber',
            'company',
            'branch',
            'role',
            'password'
        ]

    # override __init__ to dynamically filter the branch field based on the company selected
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'company' in self.data:
            try:
                company_id = int(self.data.get('company'))
                self.fields['branch'].queryset = Branch.objects.filter(company_id=company_id).order_by('name')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            self.fields['branch'].queryset = self.instance.company.branch_set.order_by('name')


class UserDetailsForm(forms.ModelForm):
    company = forms.ModelChoiceField(queryset=Company.objects.all(), required=True)
    branch = forms.ModelChoiceField(queryset=Branch.objects.none(), required=True)

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'username',
            'email',
            'phonenumber',
            'company',
            'branch',
            'role',
        ]

    # override __init__ to dynamically filter the branch field based on the company selected
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'company' in self.data:
            try:
                logger.info(f'Company: {self.data.get("company")}')
                company_id = int(self.data.get('company'))
                self.fields['branch'].queryset = Branch.objects.filter(company_id=company_id).order_by('name')
                logger.info(f'Branches: {self.fields["branch"].queryset}')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            self.fields['branch'].queryset = self.instance.company.branch_set.order_by('name')


class UserDetailsForm2(forms.ModelForm):
    edit_company = forms.ModelChoiceField(queryset=Company.objects.all(), required=True)
    edit_branch = forms.ModelChoiceField(queryset=Branch.objects.none(), required=True)

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'username',
            'email',
            'phonenumber',
            'edit_company',
            'edit_branch',
            'role',
        ]

    # override __init__ to dynamically filter the branch field based on the company selected
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'edit_company' in self.data:
            try:
                logger.info(f'Company: {self.data.get("edit_company")}')
                company_id = int(self.data.get('edit_company'))
                self.fields['edit_branch'].queryset = Branch.objects.filter(company_id=company_id).order_by('name')
                logger.info(f'Branches: {self.fields["edit_branch"].queryset}')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            self.fields['edit_branch'].queryset = self.instance.company.branch_set.order_by('name')
