from django import forms
from .models import Expense, ExpenseCategory, Customer, Currency, Invoice

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['date', 'amount', 'category', 'description', ]  
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}), 
            'description': forms.Textarea(attrs={'rows': 3}),  
        }

    def __init__(self, *args, **kwargs):
        super(ExpenseForm, self).__init__(*args, **kwargs)
        self.fields['category'].queryset = ExpenseCategory.objects.all()
        
class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = '__all__'

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = '__all__'

class CurrencyForm(forms.ModelForm):
    class Meta:
        model = Currency
        fields = '__all__'
        

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['amount_paid']