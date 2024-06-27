import datetime
from decimal import Decimal
from finance.models import Account, AccountBalance, Currency
from django.contrib import messages
from users.models import User
from django.db import transaction
from django.http import JsonResponse
from finance.forms import CashWithdrawForm
from django.utils import timezone
from finance.models import Invoice
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required
@transaction.atomic
def pos(request):
    form = CashWithdrawForm()
    invoice_count = Invoice.objects.filter(issue_date=timezone.now(), branch=request.user.branch ).count()
    
    if request.method == 'POST':
        form = CashWithdrawForm(request.POST)
        
        if form.is_valid():
            
            user_code = form.cleaned_data['user_code']
            currency = form.cleaned_data['currency']
            amount = form.cleaned_data['amount']
            
            # validations
            try:
                user = User.objects.get(code=user_code)
                currency = Currency.objects.get(id=currency)
            except User.DoesNotExist:
                messages.warning(request, 'Incorrect user code')
                return redirect('pos:pos')
            
            cw_obj = form.save(commit=False)
            cw_obj.user = user
            withdrawal = cw_obj.save()
            
            account_types = {
                'cash': Account.AccountType.CASH,
                'bank': Account.AccountType.BANK,
                'ecocash': Account.AccountType.ECOCASH,
            }

            account_name = f"{request.user.branch} {withdrawal.currency.name} {'Cash'} Account"
            
            try:
                account = Account.objects.get(name=account_name, type=Account.AccountType.CASH)
            except Account.DoesNotExist:
                messages.error(request, f'{account_name} doesnt exists')

            try:
                account_balance = AccountBalance.objects.get(account=account,  branch=request.user.branch)
            except AccountBalance.DoesNotExist:
                messages.error(request, f'Account Balances for account {account_name} doesnt exists')
                
            account_balance.balance -= Decimal(amount)
            account_balance.save()

            messages.success(request, 'Cash Withdrawal Successfully saved')
            return redirect('pos:pos')
        else:
            messages.error(request, 'Invalid form data')
            
    return render(request, 'Pos/pos.html', {'invoice_count':invoice_count, 'form':form})
