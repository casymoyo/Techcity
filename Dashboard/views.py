import datetime
from finance.models import *
from inventory.models import *
from django.db.models import Sum
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required


@login_required
def dashboard(request):
    sales = Sale.objects.filter(transaction__branch=request.user.branch).order_by('-date')[:5]
    customers = Customer.objects.all().order_by('-date')[:5]
    transfers = Transfer.objects.filter(branch = request.user.branch).order_by('-date')[:5]
    qoutations = Qoutation.objects.filter(branch=request.user.branch)
    
    invoices = Invoice.objects.filter(payment_status='Partial', branch=request.user.branch).order_by('-issue_date')[:5]

    return render(request, 'dashboard/dashboard.html', {
        'sales':sales,
        'transfers':transfers,
        'qoutations':qoutations,
        'products_count': Inventory.objects.filter(branch=request.user.branch, status=True).aggregate(total_products=Sum('quantity'))['total_products'] or 0,
        
        'customers':customers,
        'customers_count': Customer.objects.all().count(),
        'customers_today_count': Customer.objects.filter(date=datetime.date.today()).count(),
        
        'partial_invoices':invoices,
        'invoice_count': Invoice.objects.filter(branch=request.user.branch, status=True).count(),
        'invoice_today_count': Invoice.objects.filter(branch=request.user.branch, issue_date=datetime.date.today()).count(),
    })
    
@login_required
def get_partial_invoice_details(request, invoice_id):
    invoices = Invoice.objects.filter(payment_status='Partial', id=invoice_id, branch=request.user.branch).order_by('-issue_date').values()
    return JsonResponse(list(invoices), safe=False)


@login_required
def POS(request):
    return render(request, 'dashboard/dashboard.html')