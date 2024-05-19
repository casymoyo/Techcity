from finance.models import *
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def dashboard(request):
    sales = Sale.objects.filter(transaction__branch=request.user.branch)
    invoices = Invoice.objects.filter(payment_status='Partial', branch=request.user.branch)
    
    return render(request, 'dashboard/dashboard.html', {
        'sales':sales,
        'partial_invoices':invoices
    })

@login_required
def POS(request):
    return render(request, 'dashboard/dashboard.html')