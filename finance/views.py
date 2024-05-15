from .models import *
import json, datetime
from decimal import Decimal
from django.views import View
from django.db.models import Q
from django.utils import timezone
from django.db import transaction
from django.contrib import messages
from utils.utils import generate_pdf
from django.http import JsonResponse
from inventory.models import Inventory
from inventory.models import ActivityLog
from . utils import calculate_expenses_totals
from django.utils.dateparse import parse_date
from django.db.models import Sum, DecimalField
from django.http import JsonResponse, HttpResponse
from . forms import ExpenseForm, ExpenseCategoryForm
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404, redirect

class Finance(View):
    template_name = 'finance/finance.html'

    def get(self, request, *args, **kwargs):
        # Balances
        cash_balance = CashAccount.objects.aggregate(total_balance=Sum('balance'))['total_balance'] or 0
        bank_balance = BankAccount.objects.aggregate(total_balance=Sum('balance'))['total_balance'] or 0

        # Recent Transactions
        recent_transactions = Transaction.objects.all().order_by('-date')[:10]
        
        # Pay laters 
        pay_later_transactions = PayLaterTransaction.objects.all().order_by('-paid_date')[:10]

        # 3. Expense Summary (Optional)
        expenses_by_category = Expense.objects.values('category__name').annotate(
            total_amount=Sum('amount', output_field=DecimalField())
        )
        
        context = {
            'cash_balance': cash_balance,
            'bank_balance': bank_balance,
            'recent_transactions': recent_transactions,
            'expenses_by_category': expenses_by_category,
            'pay_later_transactions':pay_later_transactions
        }
        return render(request, self.template_name, context)

class ExpenseView(View):
    form_class = ExpenseForm
    template_name = 'finance/expenses/expense_form.html'

    def get(self, request, pk=None):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            expenses = Expense.objects.all().values(
                'id', 'date', 'description', 'amount', 'category__name'
            )
            return JsonResponse(list(expenses))
        elif pk:
            expense = get_object_or_404(Expense, pk=pk)
            form = self.form_class(instance=expense)
            return render(request, self.template_name, {'form': form, 'expense': expense})
        else:
            expenses = Expense.objects.all().order_by('-date')
            expense_categories = ExpenseCategory.objects.all()
            
            start_date_str = request.GET.get('start_date')
            end_date_str = request.GET.get('end_date')
            category_id = request.GET.get('category')

            if start_date_str:
                start_date = parse_date(start_date_str)
                expenses = expenses.filter(date__gte=start_date)
            if end_date_str:
                end_date = parse_date(end_date_str)
                expenses = expenses.filter(date__lte=end_date)
            if category_id:
                expenses = expenses.filter(category_id=category_id)
                
            form = self.form_class()
            
            return render(request, 'finance/expense_list.html', {
                'form': form,
                'expenses': expenses.order_by('-date'),
                'expense_categories': expense_categories,
                })

    def post(self, request, pk=None):
        if pk:
            expense = get_object_or_404(Expense, pk=pk)
            form = ExpenseForm(request.POST, instance=expense)
            if form.is_valid():
                form.save()
                messages.success(request, 'Expense edited successfully')
                return redirect('finance:expense_list')
        else:
            form = ExpenseForm(request.POST)

        if form.is_valid():
            expense = form.save(commit=False)
            expense.branch = request.user.branch
            expense.save()
            messages.success(request, 'Expense successfuly created')
            return redirect('finance:expense_list')
        else:
            return render(request, self.template_name, {'form': form})

    def delete(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        expense.delete()
        return redirect('finance:expenses_list')
    

def create_expense(request):
    form = ExpenseCategoryForm()
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        
        if form.is_valid():
            expense = form.save(commit=False)
            expense.branch = request.user.branch
            expense.save()
            
            messages.success(request, 'Expense successfuly created')
            return redirect('finance:expense_list')

    return render(request, 'finance/expenses/add_expense.html', {'form': form})

def create_expense_category(request):
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST) 
        
        if ExpenseCategory.objects.filter(name=request.POST['name']).exists():
            return JsonResponse({ 'message': 'Category exists'})
        
        if form.is_valid():
            category = form.save()
            return JsonResponse({
                'message': 'Expense category created successfully!',
                'category_id': category.pk
            })
        else:
            return JsonResponse({
                'errors': form.errors,
                'message': 'Expense category creation failed. Please check the errors.'
            }, status=400)  

    return JsonResponse({'message': 'Invalid request method.'}, status=405)

        
def invoice(request):
    invoices = Invoice.objects.filter(branch=request.user.branch).order_by('issue_date')
    
    total_draft = invoices.filter(payment_status='Draft').aggregate(Sum('amount'))['amount__sum'] or 0
    total_pending = invoices.filter(payment_status='Pending').aggregate(Sum('amount'))['amount__sum'] or 0
    total_partial = invoices.filter(payment_status='Partial').aggregate(Sum('amount'))['amount__sum'] or 0
    total_paid = invoices.filter(payment_status='Paid').aggregate(Sum('amount'))['amount__sum'] or 0
    total_overdue = invoices.filter(payment_status='Overdue').aggregate(Sum('amount'))['amount__sum'] or 0
    total_amount = invoices.aggregate(Sum('amount'))['amount__sum'] or 0
    print(total_pending)
    return render(request, 'finance/invoices/invoice.html', 
        {
            'invoices':invoices,
            'total_pending':total_pending,
            'total_paid':total_paid,
            'total_overdue':total_paid,
            'total_amount':total_amount
        }
    )

def process_invoice(request, invoice_id):
    try:
        with transaction.atomic():
            invoice = get_object_or_404(Invoice, pk=invoice_id)
            invoice_items = InvoiceItem.objects.filter(invoice=invoice)
            amount_paid = Decimal(request.POST.get('amount_paid')) 

            if invoice.payment_status != Invoice.PaymentStatus.PAID:
                amount_paid = Decimal(request.POST.get('amount_paid')) 

                # Validate amount_paid (should not exceed amount_due)
                if amount_paid <= 0 or amount_paid > invoice.amount_due:
                    messages.error(request, 'Invalid payment amount.')
                    return redirect('finance:invoice_detail', pk=invoice_id)
                
                #vat mount
                vat_amount = invoice.vat
            
                # Get or create cashAccount and VAT output account
                cash_account, _ = CashAccount.objects.get_or_create(name="Cash")
                vat_output_account, _ = ChartOfAccounts.objects.get_or_create(name="VAT Output")
                
                # Create Transaction to record payment to bank account
                transaction_obj = Transaction.objects.create(
                    date=timezone.now(),
                    description=f"Payment for Invoice #{invoice.invoice_number}",
                    account=cash_account,
                    content_type=ContentType.objects.get_for_model(CashAccount),
                    object_id=cash_account.id,
                    debit=amount_paid,
                    credit=Decimal('0.00'),
                    customer=invoice.customer
                )

                # Create Sale object
                sale = Sale.objects.create(
                    date=timezone.now(),
                    customer=invoice.customer,
                    transaction=transaction_obj,
                    amount=invoice.amount,
                )

                # Create Receipt object
                receipt = Receipt.objects.create(
                    transaction=transaction,
                    date=timezone.now()
                )

                # Create ReceiptItem objects for each item in the invoice
                for item in invoice_items:
                    ReceiptItem.objects.create(
                        receipt=receipt,
                        item=item.item,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                    )

                # Update stock quantities based on sold items
                for item in invoice_items:
                    stock_item = item.item
                    stock_item.quantity -= item.quantity
                    stock_item.save()

                    # Create StockTransaction for each sold item
                    stock_transaction = StockTransaction.objects.create(
                        item=stock_item,
                        transaction_type=StockTransaction.TransactionType.SALE,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        date=timezone.now(),
                        receipt_content_type=ContentType.objects.get_for_model(BankAccount),
                        receipt_object_id=cash_account.id
                    )
                    
                    # Create VATTransaction
                    VATTransaction.objects.create(
                        transaction=transaction_obj,
                        stock_transaction=stock_transaction,
                        vat_type=VATTransaction.VATType.OUTPUT,
                        vat_rate=VATRate.objects.get(status=True).rate,
                        tax_amount=item.vat_amount
                    )
                    
                    # create inventory log
                    ActivityLog(
                        branch=request.user.branch,
                        inventory=item.item,
                        user=request.user,
                        quantity=item.quantity,
                        total_quantity = item.item.quantity
                    )
                
                # Update the Invoice's status
                invoice.amount_paid += amount_paid
                invoice.amount_due -= amount_paid
                
                # Update cash account
                cash_account.balance += amount_paid 
                cash_account.save()

        
                if invoice.amount_due == 0:
                    invoice.payment_status = Invoice.PaymentStatus.PAID
                else:
                    invoice.payment_status = Invoice.PaymentStatus.PARTIAL
                
                invoice.save()
                
            else:
                messages.error(request, 'Invoice has already been paid')
                return redirect('finance:invoice')

    except Invoice.DoesNotExist:
        messages.error(request, 'Invoice not found')
        return redirect('finance:invoice')

@csrf_exempt
def create_invoice(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            invoice_data = data['data'][0]  
            items_data = data['items']
            
            print(items_data)
            
            cash_account, _ = CashAccount.objects.get_or_create(name="Cash")
            vat_output_account, _ = ChartOfAccounts.objects.get_or_create(name="VAT Output")

            # Create invoice object
            customer = Customer.objects.get(id=int(invoice_data['client_id'])) 
            print(customer)
            accounts_receivable, _ = ChartOfAccounts.objects.get_or_create(name="Accounts Receivable")
            
            invoice_total_amount = Decimal(invoice_data['payable']) + Decimal(invoice_data['vat_amount'])
            
            invoice = Invoice.objects.create(
                invoice_number=Invoice.generate_invoice_number(),  
                customer=customer,
                issue_date=timezone.now(),
                due_date=timezone.now() + timezone.timedelta(days=int(invoice_data['days'])),
                amount=invoice_total_amount,
                amount_paid=Decimal(invoice_data['payable']),
                vat=Decimal(invoice_data['vat_amount']),
                payment_status = Invoice.PaymentStatus.DUE if invoice_total_amount < Decimal(invoice_data['payable']) else Invoice.PaymentStatus.PAID,
                branch = request.user.branch

            )
            
            # #create transaction
            transaction_obj = Transaction.objects.create(
                date=timezone.now(),
                description=invoice_data['note'],
                account=accounts_receivable,
                debit=Decimal(invoice_data['payable']),
                credit=Decimal('0.00'),
                customer=customer
            )
            
            # Create InvoiceItem objects
            for item_data in items_data:
                item = Inventory.objects.get(pk=item_data['inventory_id'])
                
                item.quantity -= item_data['quantity']
                item.save()
                
                
                InvoiceItem.objects.create(
                    invoice=invoice,
                    item=item,
                    quantity=item_data['quantity'],
                    unit_price=item_data['price']
                )
                
                # Create StockTransaction for each sold item
                stock_transaction = StockTransaction.objects.create(
                    item=item,
                    transaction_type=StockTransaction.TransactionType.SALE,
                    quantity=item.quantity,
                    unit_price=item.price,
                    date=timezone.now(),
                    receipt_content_type=ContentType.objects.get_for_model(CashAccount),
                    receipt_object_id=cash_account.id
                    )
                
                # stock log  
                ActivityLog(
                        branch=request.user.branch,
                        inventory=item.item,
                        user=request.user,
                        quantity=item_data['quantity'],
                        total_quantity = item.quantity
                    )
                
            # # Create VATTransaction
            VATTransaction.objects.create(
                transaction=transaction_obj,
                stock_transaction=stock_transaction,
                vat_type=VATTransaction.VATType.OUTPUT,
                vat_rate=VATRate.objects.get(status=True).rate,
                tax_amount=item.vat_amount
            )
            
            # Create Sale object
            sale = Sale.objects.create(
                date=timezone.now(),
                customer=invoice.customer,
                transaction=transaction_obj,
            )
            
            # Update cash account
            cash_account.balance += Decimal(invoice_data['payable']),
            cash_account.save()

            return JsonResponse({'success': True, 'invoice_id': 'invoice.id'})
            

        except (KeyError, json.JSONDecodeError, Customer.DoesNotExist, Inventory.DoesNotExist) as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return render(request, 'finance/invoices/add_invoice.html')



# Reports
def expenses_report(request):
    
    template_name = 'finance/reports/expenses.html'
    
    search = request.GET.get('search', '')
    start_date_str = request.GET.get('startDate', '')
    end_date_str = request.GET.get('endDate', '')
    category_id = request.GET.get('category', '')
    print(category_id)
    
   
    if start_date_str and end_date_str:
        try:
            end_date = datetime.date.fromisoformat(end_date_str)
            start_date = datetime.date.fromisoformat(start_date_str)
        except ValueError:
            return JsonResponse({'messgae':'Invalid date format. Please use YYYY-MM-DD.'})
    else:
        start_date = ''
        end_date= ''
        
    try:
        category_id = int(category_id) if category_id else None
    except ValueError:
        return JsonResponse({'messgae':'Invalid category or search ID.'})

    expenses = Expense.objects.all()  
    
    if search:
        expenses = expenses.filter(Q('amount=search'))
    if start_date:
        start_date = parse_date(start_date_str)
        expenses = expenses.filter(date__gte=start_date)
    if end_date:
        end_date = parse_date(end_date_str)
        expenses = expenses.filter(date__lte=end_date)
    if category_id:
        print('here')
        expenses = expenses.filter(category__id=category_id)
    
    print(expenses)
    return generate_pdf(
        template_name,
        {
            'title': 'Expenses', 
            'date_range': f"{start_date} to {end_date}", 
            'report_date': datetime.date.today(),
            'total_expenses':calculate_expenses_totals(expenses),
            'expenses':expenses
        }
    )

def invoice_pdf(request):
    template_name = 'finance/reports/invoice.html'
    invoice_id = request.GET.get('id', '')
    if invoice_id:
        try:
            invoice = get_object_or_404(Invoice, pk=invoice_id)

            invoice_items = InvoiceItem.objects.filter(invoice=invoice)
            
        except Invoice.DoesNotExist:
            return HttpResponse("Invoice not found", status=404)
    else:
        return HttpResponse("Invoice ID is required", status=400)
    
    return generate_pdf(
        template_name,
        {
            'title': 'Invoice', 
            'report_date': datetime.date.today(),
            'invoice':invoice,
            'invoice_items':invoice_items
        }
    )