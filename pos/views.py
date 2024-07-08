import datetime
from django.db import transaction
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
            
    return render(request, 'Pos/pos.html', {'invoice_count':invoice_count, 'form':form})
