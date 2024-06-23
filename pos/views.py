import datetime
from django.contrib import messages
from users.models import User
from django.http import JsonResponse
from finance.forms import CashWithdrawForm
from django.utils import timezone
from finance.models import Invoice
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required
def pos(request):
    form = CashWithdrawForm()
    invoice_count = Invoice.objects.filter(issue_date=timezone.now(), branch=request.user.branch ).count()
    
    if request.method == 'POST':
        form = CashWithdrawForm(request.POST)
        
        if form.is_valid():
            
            user_code = form.cleaned_data['user_code']
            
            # validations
            try:
                user = User.objects.get(code=user_code)
            except User.DoesNotExist:
                messages.warning(request, 'Incorrect user code')
                return redirect('pos:pos')
            
            cw_obj = form.save(commit=False)
            cw_obj.user = user
            cw_obj.save()

            messages.success(request, 'Cash Withdrawal Successfully saved')
            return redirect('pos:pos')
        else:
            messages.error(request, 'Invalid form data')
            
    return render(request, 'Pos/pos.html', {'invoice_count':invoice_count, 'form':form})
