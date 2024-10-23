import os
import datetime
from django.http import JsonResponse
from django.db import transaction
from finance.forms import CashWithdrawForm
from django.utils import timezone
from finance.models import Invoice
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from loguru import logger

@login_required
@transaction.atomic
def pos(request):
    form = CashWithdrawForm()
    invoice_count = Invoice.objects.filter(issue_date=timezone.now(), branch=request.user.branch ).count()
            
    return render(request, 'Pos/pos.html', {'invoice_count':invoice_count, 'form':form})

@login_required
def process_receipt(request):
    pass    

@login_required
def last_due_invoice(request, customer_id):
    invoice = Invoice.objects.filter(customer__id=customer_id, payment_status=Invoice.PaymentStatus.PARTIAL)\
            .order_by('-issue_date').values('invoice_number')
    logger.info(invoice)
    return JsonResponse(list(invoice), safe=False)


def upload_file():
    file = request.files['file']
    file_path = os.path.join('uploads', file.filename)
    file.save(file_path)
    return JsonResponse({"status": "success", "file_path": file_path}), 200
