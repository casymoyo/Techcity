import datetime
from django.utils import timezone
from finance.models import Invoice
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def pos(request):
    invoice_count = Invoice.objects.filter(issue_date=timezone.now(), branch=request.user.branch ).count()
    return render(request, 'Pos/pos.html', {'invoice_count':invoice_count})
