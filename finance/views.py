from .models import *
import json, datetime
from decimal import Decimal
from django.views import View
from django.db.models import Q
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.contrib import messages
from utils.utils import generate_pdf
from django.http import JsonResponse
from inventory.models import Inventory
from . utils import calculate_expenses_totals
from django.utils.dateparse import parse_date
from django.db.models import Sum, DecimalField
from inventory.models import ActivityLog, Product
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404, redirect
from . forms import ExpenseForm, ExpenseCategoryForm, CustomerForm, CurrencyForm, InvoiceForm

class Finance(View):
    template_name = 'finance/finance.html'

    def get(self, request, *args, **kwargs):
        # Balances
        cash_balance = CashAccount.objects.aggregate(total_balance=Sum('balance'))['total_balance'] or 0
        bank_balance = BankAccount.objects.aggregate(total_balance=Sum('balance'))['total_balance'] or 0

        # Recent Transactions
        recent_transactions = Transaction.objects.all().order_by('-date')[:5]
       

        # 3. Expense Summary (Optional)
        expenses_by_category = Expense.objects.values('category__name').annotate(
            total_amount=Sum('amount', output_field=DecimalField())
        )
        
        context = {
            'cash_balance': cash_balance,
            'bank_balance': bank_balance,
            'recent_transactions': recent_transactions,
            'expenses_by_category': expenses_by_category,
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
            expense.user = request.user
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
    day = request.GET.get('day', '')
    q = request.GET.get('q', '')
    
    invoices = Invoice.objects.filter(branch=request.user.branch, status=True).order_by('-issue_date')
    today = timezone.now().date()  
    
    if q:
        invoices = invoices.filter(
            Q(customer__name__icontains=q)|
            Q(invoice_number__icontains=q)|
            Q(issue_date__icontains=q)
        )

    if day == 'today':
        invoices = invoices.filter(issue_date=today)

    if day == 'yesterday':
        yesterday = today - timedelta(days=1)
        invoices = invoices.filter(issue_date=yesterday)

    if day == 't_week':
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        invoices = invoices.filter(issue_date__range=[start_of_week, end_of_week])

    if day == 'l_week':
        end_of_last_week = today - timedelta(days=today.weekday() + 1)
        start_of_last_week = end_of_last_week - timedelta(days=6)
        invoices = invoices.filter(issue_date__range=[start_of_last_week, end_of_last_week])

    if day == 't_month':
        invoices = invoices.filter(issue_date__month=today.month, issue_date__year=today.year)

    if day == 'l_month':
        last_month = today.month - 1 if today.month > 1 else 12
        last_month_year = today.year if today.month > 1 else today.year - 1
        invoices = invoices.filter(issue_date__month=last_month, issue_date__year=last_month_year)

    if day == 't_year':
        invoices = invoices.filter(issue_date__year=today.year)

    total_partial = invoices.filter(payment_status='Partial').aggregate(Sum('amount'))['amount__sum'] or 0
    total_paid = invoices.filter(payment_status='Paid').aggregate(Sum('amount'))['amount__sum'] or 0
    total_amount = invoices.aggregate(Sum('amount'))['amount__sum'] or 0

    return render(request, 'finance/invoices/invoice.html', {
        'search_query':q,
        'invoices': invoices,
        'total_paid': total_paid,
        'total_due': total_partial,
        'total_amount': total_amount, 
    })

def update_invoice(request, invoice_number):
    form = InvoiceForm()
    invoice = Invoice.objects.get(invoice_number=invoice_number)
    customer_account = CustomerAccount.objects.get(customer__id=invoice.customer.id)
    
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        
        if form.is_valid():
            amount_paid = Decimal(request.POST['amount_paid'])
            
            if amount_paid < 0:
                messages.error(request, 'Amount cant be below zero')
                return render(request, 'finance/invoices/update_invoice.html', {'form':form})
            
            if amount_paid >= invoice.amount_due:
                invoice.payment_status=invoice.PaymentStatus.PAID
                invoice.amount_due = 0
            else:
                invoice.amount_due -= amount_paid
              
            invoice.amount_paid += amount_paid   
              
            Payment.objects.create(
                invoice=invoice,
                amount_paid=amount_paid,
                payment_method="Cash"
            )
            
            customer_account.balance -= amount_paid
            customer_account.save()
            invoice.save()
            messages.success(request, 'Invoice successfully updated')
            return redirect('finance:invoice')
    return render(request, 'finance/invoices/update_invoice.html', {'form':form, 'invoice':invoice})

def create_invoice(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            invoice_data = data['data'][0]  
            items_data = data['items']
           
            # get cash account
            cash_account, _ = CashAccount.objects.get_or_create(name="Cash")
            
            # get accountts_receivable
            accounts_receivable, _ = ChartOfAccounts.objects.get_or_create(name="Accounts Receivable")
            
            # get currency
            currency = Currency.objects.get(id=invoice_data['currency'])

            # get VAT rate
            vat_rate = VATRate.objects.get(status=True)

            # customer
            customer = Customer.objects.get(id=int(invoice_data['client_id'])) 
            
            # get customer account
            customer_account = CustomerAccount.objects.get(customer=customer)
            
            
            amount_paid = Decimal(invoice_data['amount_paid'])
            invoice_total_amount = Decimal(invoice_data['payable'])
            
            # check for due invoices 
            if Invoice.objects.filter(customer=customer, payment_status='Partial', branch=request.user.branch).exists():
                due_invoice = Invoice.objects.filter(customer=customer, payment_status='Partial', branch=request.user.branch).last()
                if amount_paid > due_invoice.amount_due:
                    due_invoice.amount_paid += due_invoice.amount_due
                    amount_paid -= due_invoice.amount_due
                    due_invoice.payment_status= due_invoice.PaymentStatus.PAID
                    
                    
                    # refactor
                    Payment.objects.create(
                        invoice=due_invoice,
                        amount_paid=due_invoice.amount_due,
                        payment_method='Cash'
                    )
                    
                    customer_account.balance -= due_invoice.amount_due
                    due_invoice.amount_due = 0
                    print(customer_account.balance, due_invoice.amount_due)
                    
                else:
                    due_invoice.amount_due -= amount_paid
                    due_invoice.amount_paid += amount_paid
                    
                    Payment.objects.create(
                        invoice=due_invoice,
                        amount_paid=amount_paid,
                        payment_method='Cash'
                    )
        
                    customer_account.balance -= amount_paid
                    amount_paid = 0
                
                customer_account.save()
                due_invoice.save()

            # calculate amount due
            amount_due = invoice_total_amount - amount_paid
            
            with transaction.atomic():
            
                invoice = Invoice.objects.create(
                    invoice_number=Invoice.generate_invoice_number(request.user.branch.name),  
                    customer=customer,
                    issue_date=timezone.now(),
                    due_date=timezone.now() + timezone.timedelta(days=int(invoice_data['days'])),
                    amount=invoice_total_amount,
                    amount_paid=amount_paid,
                    amount_due=amount_due,
                    discount_amount=invoice_data['discount'],
                    delivery_charge=invoice_data['delivery'],
                    vat=Decimal(invoice_data['vat_amount']),
                    payment_status = Invoice.PaymentStatus.PARTIAL if amount_due > 0 else Invoice.PaymentStatus.PAID,
                    branch = request.user.branch,
                    user=request.user,
                    currency=currency,
                    subtotal=invoice_data['subtotal']
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
                    product = Product.objects.get(pk=item.product.id)
                    
                    item.quantity -= item_data['quantity']
                    item.save()
                  
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        item=item,
                        quantity=item_data['quantity'],
                        unit_price=item_data['price'],
                        vat_rate = vat_rate
                    )
                    
                    # Create StockTransaction for each sold item
                    stock_transaction = StockTransaction.objects.create(
                        item=product,
                        transaction_type=StockTransaction.TransactionType.SALE,
                        quantity=item.quantity,
                        unit_price=item.price,
                        date=timezone.now()
                        )
                    
                    # stock log  
                    ActivityLog.objects.create(
                            branch=request.user.branch,
                            inventory=item,
                            user=request.user,
                            quantity=item_data['quantity'],
                            total_quantity = item.quantity,
                            action='Sale'
                        )
                    
                # # Create VATTransaction
                VATTransaction.objects.create(
                    transaction=transaction_obj,
                    stock_transaction=stock_transaction,
                    vat_type=VATTransaction.VATType.OUTPUT,
                    vat_rate=VATRate.objects.get(status=True).rate,
                    tax_amount=invoice_data['vat_amount']
                )
                
                # Create Sale object
                sale = Sale.objects.create(
                    date=timezone.now(),
                    transaction=invoice,
                    total_amount=invoice_total_amount
                )
                
                #payment
                Payment.objects.create(
                    invoice=invoice,
                    amount_paid=amount_paid,
                    payment_method='Cash'
                )
                
                # updae account balance
                if invoice.payment_status == 'Partial':
                    customer_account.balance += amount_due
                    customer_account.save()
                    
                # Update cash  account
                cash_account.balance = Decimal(invoice_data['payable']) + Decimal(cash_account.balance)
                cash_account.save()
                
                return JsonResponse({'success': True, 'invoice_id': 'invoice.id'})
            

        except (KeyError, json.JSONDecodeError, Customer.DoesNotExist, Inventory.DoesNotExist) as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return render(request, 'finance/invoices/add_invoice.html')

def customer(request):
    customers = CustomerAccount.objects.all().values(
        'customer__id',
        'customer__name', 
        'customer__phone_number', 
        'customer__address', 
        'balance'
    )
    
    if request.method == 'POST':
        data = json.loads(request.body)
        
        customer = Customer.objects.create(
            name=data['name'],
            email=data['email'],
            address=data['address'],
            phone_number=data['phonenumber']
        )
        
        CustomerAccount.objects.create(
            customer=customer,
            balance=0
        )
        return JsonResponse({'success': True, 'message': 'Customer succesfully created'})
    return JsonResponse(list(customers), safe=False)
    
def customer_account(request, customer_id):
    q = request.GET.get('q', '')
    search_query = request.GET.get('search_query', '')
    
    customer = Customer.objects.get(id=customer_id)
    account = CustomerAccount.objects.get(customer=customer)
    invoices = Invoice.objects.filter(customer=customer, branch=request.user.branch, status=True)
    
    if q:
        invoices = invoices.filter(payment_status=q)
    if search_query:
        invoices = invoices.filter(Q(invoice_number__icontains=search_query) | Q(issue_date__icontains=search_query) )

    
    return render(request, 'finance/customer.html', {
        'q':q,
        'account':account,
        'invoices':invoices,
        'customer':customer,
        'search_query':search_query,
        'paid':Invoice.objects.filter(payment_status='Paid', customer=customer, branch=request.user.branch, status=True).count(),
        'due':Invoice.objects.filter(payment_status='Partial', customer=customer, branch=request.user.branch, status=True).count(),
    })

# currency views    
def currency(request):
    currencies = Currency.objects.all()
    return render(request, 'finance/currency/currency.html')

def currency_json(request):
    currency_id = request.GET.get('id', '')
    currency = Currency.objects.filter(id=currency_id).values()
    return JsonResponse(list(currency), safe=False)


def add_currency(request):
    form = CurrencyForm()
    if request.method == 'POST':
        form = CurrencyForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Currency successfully created')
            return redirect('finance:currency')
    return render(request, 'finance/currency/currency_add.html', {'form':form})

def update_currency(request, currency_id):
    try:
        currency = Currency.objects.get(id=currency_id)
    except Currency.DoesNotExist:
        messages.error(request, 'Currency doesnt Exists')
        return redirect('finance:currency')
    
    form = CurrencyForm(instance=currency)
    
    if form.is_valid():
        form.save()
        messages.success(request, 'Currency successfully created')
        return redirect('finance:currency')
    return render(request, 'finance/currency/currency_add.html', {'form':form})

def delete_currency(request, currency_id):
    try:
        currency = Currency.objects.get(id=currency_id)
        currency.delete()
    except Currency.DoesNotExist:
        messages.error(request, 'Currency doesnt Exists')
        return JsonResponse({'message':'Currency doesnt exists'})
    return JsonResponse({'message':'Deleted Successfully'})

def finance_settings(request):
    return render(request, 'finance/settings/settings.html')
    
# Reports
def expenses_report(request):
    
    template_name = 'finance/reports/expenses.html'
    
    search = request.GET.get('search', '')
    start_date_str = request.GET.get('startDate', '')
    end_date_str = request.GET.get('endDate', '')
    category_id = request.GET.get('category', '')
   
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
        expenses = expenses.filter(category__id=category_id)
    
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
    
def invoice_preview(request, invoice_id):
    invoice = Invoice.objects.get(id=invoice_id)
    invoice_items = InvoiceItem.objects.filter(invoice=invoice)
    account = CustomerAccount.objects.get(customer__id = invoice.customer.id)
    return render(request, 'pos/receipt.html', {'invoice':invoice, 'invoice_items':invoice_items,'account': account})

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