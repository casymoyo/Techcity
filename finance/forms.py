from django import forms
from .models import (
    Expense, 
    ExpenseCategory, 
    Customer, 
    Currency, 
    Invoice, 
    CashTransfers, 
    CashWithdraw, 
    CustomerDeposits,
    CashDeposit
)

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['payment_method', 'currency', 'amount', 'category', 'description', ] 

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
        exclude = ['branch']

class CurrencyForm(forms.ModelForm):
    class Meta:
        model = Currency
        fields = '__all__'
        

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['amount_paid']
        
class TransferForm(forms.ModelForm):
    class Meta:
        model = CashTransfers
        exclude = ['user', 'from_branch', 'branch', 'received_status']
        

class CashWithdrawForm(forms.ModelForm):
    class Meta:
        model = CashWithdraw
        fields = ['amount', 'currency', 'reason', 'password'] 
    password = forms.CharField(widget=forms.PasswordInput)

class cashWithdrawExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields= ['currency', 'amount', 'category', 'description']     

class customerDepositsForm(forms.ModelForm):
    class Meta:
        model = CustomerDeposits
        exclude = ['cashier', 'customer_account', 'branch']

class customerDepositsRefundForm(forms.ModelForm):
    class Meta:
        model = CustomerDeposits
        fields = ['amount',]

class cashDepositForm(forms.ModelForm):
    class Meta:
        model = CashDeposit
        exclude = ['user']
   
