import datetime
from finance.models import Invoice
from django.shortcuts import render

def pos(request):
    invoice_count = Invoice.objects.filter(issue_date=datetime.date.today()).count()
    return render(request, 'pos/pos.html', {'invoice_count':invoice_count})
