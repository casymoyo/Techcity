from .models import *
from decimal import Decimal
from io import BytesIO
from .consumers import CashTransferConsumer 
from xhtml2pdf import pisa 
from django.views import View
from django.db.models import Q
from twilio.rest import Client
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.contrib import messages
from utils.utils import generate_pdf
from django.http import JsonResponse
from utils.utils import generate_pdf
from celery.result import AsyncResult
from asgiref.sync import async_to_sync, sync_to_async
from inventory.models import Inventory
from channels.layers import get_channel_layer
import json, datetime, os, boto3, openpyxl 
from .tasks import send_invoice_email_task
from pytz import timezone as pytz_timezone 
from openpyxl.styles import Alignment, Font
from . utils import calculate_expenses_totals
from django.utils.dateparse import parse_date
from django.templatetags.static import static
from django.db.models import Sum, DecimalField
from inventory.models import ActivityLog, Product
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.core.mail import send_mail, EmailMessage
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from . forms import ExpenseForm, ExpenseCategoryForm, CurrencyForm, InvoiceForm, CustomerForm, TransferForm

import logging

logger = logging.getLogger(__name__)

class Finance(View):
    template_name = 'finance/finance.html'

    def get(self, request, *args, **kwargs):
        # Balances
        balances = AccountBalance.objects.filter(branch=request.user.branch)
        
        # Recent Transactions
        recent_sales = Sale.objects.filter(transaction__branch=request.user.branch).order_by('-date')[:5]

        # 3. Expense Summary (Optional)
        expenses_by_category = Expense.objects.values('category__name').annotate(
            total_amount=Sum('amount', output_field=DecimalField())
        )
        
        context = {
            'balances': balances,
            'recent_transactions': recent_sales,
            'expenses_by_category': expenses_by_category,
        }
        return render(request, self.template_name, context)

class ExpenseView(View):
    form_class = ExpenseForm
    template_name = 'finance/expenses/expense_form.html'

    def get(self, request, pk=None):
        if pk:
            expense = get_object_or_404(Expense, pk=pk)
            form = self.form_class(instance=expense)
            return render(request, self.template_name, {'form': form, 'expense': expense})
        else:
            expenses = Expense.objects.filter(branch=request.user.branch).order_by('-date')
            expense_categories = ExpenseCategory.objects.all()
            
            search_query = request.GET.get('q','')
            category_id = request.GET.get('category', '')

            if category_id:
                expenses = expenses.filter(category_id=category_id)
            
            if search_query:
                expenses = expenses.filter(Q(amount__icontains=search_query)|Q(description__icontains=search_query))
                
            form = self.form_class()
            
            return render(request, 'finance/expense_list.html', {
                'search_query':search_query,
                'category':category_id,
                'form': form,
                'expenses': expenses,
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
    
@login_required
def create_expense(request):
    form = ExpenseForm()
    expense_category_form = ExpenseCategoryForm() 
    if request.method == 'POST':
        form = ExpenseForm(request.POST)

        if form.is_valid():
            expense = form.save(commit=False)
            expense.date = datetime.date.today()  
            expense.branch = request.user.branch
            expense.user = request.user
            expense.save()

            messages.success(request, 'Expense successfully created!')
            return redirect('finance:expense_list')  

        else:
            messages.error(request, "Invalid form data. Please correct the errors.")  

    return render(request, 'finance/expenses/add_expense.html', {'form': form, 'expense_category_form': expense_category_form}) 


@login_required
@transaction.atomic  
def confirm_expense(request, expense_id):
    expense = Expense.objects.get(id=expense_id)
    
    account_types = {
            'cash': Account.AccountType.CASH,
            'bank': Account.AccountType.BANK,
            'ecocash': Account.AccountType.ECOCASH,
        }

    account_name = f"{request.user.branch} {expense.currency.name} {expense.payment_method.capitalize()} Account"
    
    try:
        account = Account.objects.get(name=account_name, type=account_types[expense.payment_method])
    except Account.DoesNotExist:
        messages.error(request, f'{account_name} doesnt exists')
        return redirect('finance:expense_list')
    try:
        account_balance = AccountBalance.objects.get(account=account,  branch=request.user.branch)
    except AccountBalance.DoesNotExist:
        messages.error(request, f'Account Balances for account {account_name} doesnt exists')
        return redirect('finance:expense_list')
    
    account_balance.balance -= Decimal(expense.amount)
    
    expense.status=True
    
    expense.save()
    account_balance.save()
    
    messages.success(request, 'Expense confirmed')
    return redirect('finance:expense_list')

    

@login_required
def create_expense_category(request):
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST)

        if ExpenseCategory.objects.filter(
            name__iexact=request.POST['name'] 
        ).exists():
            return JsonResponse({'message': 'Category already exists.'})  

        if form.is_valid():
            category = form.save()
            return JsonResponse({
                'message': 'Expense category created successfully!'
            })
        else:
            return JsonResponse({
                'errors': form.errors,  
                'message': 'Expense category creation failed. Please check the errors.'
            })
        
    return JsonResponse({'message': 'Invalid request method.'}) 


@login_required
def invoice(request):
    form = InvoiceForm()
    invoices = Invoice.objects.filter(branch=request.user.branch, status=True).order_by('-issue_date')
    
    query_params = request.GET
    if query_params.get('q'):
        search_query = query_params['q']
        invoices = invoices.filter(
            Q(customer__name__icontains=search_query) |
            Q(invoice_number__icontains=search_query) |
            Q(issue_date__icontains=search_query)
        )

    user_timezone_str = request.user.timezone if hasattr(request.user, 'timezone') else 'UTC'
    user_timezone = pytz_timezone(user_timezone_str)  

    def filter_by_date_range(start_date, end_date):
        start_datetime = user_timezone.localize(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_datetime = user_timezone.localize(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )
        return invoices.filter(issue_date__range=[start_datetime, end_datetime])

    now = timezone.now().astimezone(user_timezone)
    today = now.date()

    now = timezone.now() 
    today = now.date()  
    date_filters = {
        'today': lambda: filter_by_date_range(today, today),
        'yesterday': lambda: filter_by_date_range(today - timedelta(days=1), today - timedelta(days=1)),
        't_week': lambda: filter_by_date_range(today - timedelta(days=today.weekday()), today),
        'l_week': lambda: filter_by_date_range(today - timedelta(days=today.weekday() + 7), today - timedelta(days=today.weekday() + 1)),
        't_month': lambda: invoices.filter(issue_date__month=today.month, issue_date__year=today.year),
        'l_month': lambda: invoices.filter(issue_date__month=today.month - 1 if today.month > 1 else 12, issue_date__year=today.year if today.month > 1 else today.year - 1),
        't_year': lambda: invoices.filter(issue_date__year=today.year),
    }

    if query_params.get('day') in date_filters:
        invoices = date_filters[query_params['day']]()

    total_partial = invoices.filter(payment_status='Partial').aggregate(Sum('amount'))['amount__sum'] or 0
    total_paid = invoices.filter(payment_status='Paid').aggregate(Sum('amount'))['amount__sum'] or 0
    total_amount = invoices.aggregate(Sum('amount'))['amount__sum'] or 0

    return render(request, 'finance/invoices/invoice.html', {
        'form': form,
        'invoices': invoices,
        'total_paid': total_paid,
        'total_due': total_partial,
        'total_amount': total_amount,
    })


@login_required
@transaction.atomic 
def update_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    customer_account = get_object_or_404(CustomerAccount, customer=invoice.customer)
    customer_account_balance = get_object_or_404(
        CustomerAccountBalances, account=customer_account, currency=invoice.currency
    )

    if request.method == 'POST':
        data = json.loads(request.body)
        amount_paid = Decimal(data['amount_paid'])

        invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
        customer_account_balance = CustomerAccountBalances.objects.select_for_update().get(pk=customer_account_balance.pk)

        if amount_paid <= 0:
            return JsonResponse({'success': False, 'message': 'Invalid amount paid.'}, status=400)

        if amount_paid >= invoice.amount_due:
            invoice.payment_status = Invoice.PaymentStatus.PAID
            invoice.amount_due = 0
        else:
            invoice.amount_due -= amount_paid

        invoice.amount_paid += amount_paid

        payment = Payment.objects.create(
            invoice=invoice,
            amount_paid=amount_paid,
            payment_method=data['payment_method'],
            user=request.user
        )

        account, _ = Account.objects.get_or_create(
            name=f"{request.user.branch} {invoice.currency.name} {payment.payment_method.capitalize()} Account",
            type=Account.AccountType[payment.payment_method.upper()] 
        )
        account_balance, _ = AccountBalance.objects.get_or_create(
            account=account,
            currency=invoice.currency,
            branch=request.user.branch,
            defaults={'balance': 0}
        )

        account_balance.balance += amount_paid
        customer_account_balance.balance -= amount_paid

        account_balance.save()
        customer_account_balance.save()
        invoice.save()
        payment.save()

        return JsonResponse({'success': True, 'message': 'Invoice successfully updated'})
    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}) 


@login_required
@transaction.atomic 
def create_invoice(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            invoice_data = data['data'][0]  
            items_data = data['items']
           
            # get currency
            currency = Currency.objects.get(id=invoice_data['currency'])
            
            # create or get accounts
            account_types = {
                'cash': Account.AccountType.CASH,
                'bank': Account.AccountType.BANK,
                'ecocash': Account.AccountType.ECOCASH,
            }

            account_name = f"{request.user.branch} {currency.name} {invoice_data['payment_method'].capitalize()} Account"

            account, _ = Account.objects.get_or_create(name=account_name, type=account_types[invoice_data['payment_method']])
            
            account_balance, _ = AccountBalance.objects.get_or_create(
                account=account,
                currency=currency,
                branch=request.user.branch,
                defaults={'balance': 0}  
            )
            
            # accountts_receivable
            accounts_receivable, _ = ChartOfAccounts.objects.get_or_create(name="Accounts Receivable")

            # VAT rate
            vat_rate = VATRate.objects.get(status=True)

            # customer
            customer = Customer.objects.get(id=int(invoice_data['client_id'])) 
            
            # customer Account + Balances
            customer_account_balance, _ = CustomerAccountBalances.objects.get_or_create(
                account__customer=customer,
                currency=currency, 
                defaults={'balance': 0}
            )
           
            
            
            amount_paid = Decimal(invoice_data['amount_paid'])
            invoice_total_amount = Decimal(invoice_data['payable'])
            
            # check for due invoices 
            if Invoice.objects.filter(customer=customer, payment_status='Partial', branch=request.user.branch, currency=currency).exists():
                due_invoice = Invoice.objects.filter(customer=customer, payment_status='Partial', branch=request.user.branch).last()
                if amount_paid > due_invoice.amount_due:
                    due_invoice.amount_paid += due_invoice.amount_due
                    amount_paid -= due_invoice.amount_due
                    due_invoice.payment_status= due_invoice.PaymentStatus.PAID
                    
                    # refactor
                    Payment.objects.create(
                        invoice=due_invoice,
                        amount_paid=due_invoice.amount_due,
                        payment_method=invoice_data['payment_method'],
                        user=request.user
                    )
                    
                    customer_account_balance.balance -= due_invoice.amount_due
                    due_invoice.amount_due = 0
                    
                else:
                    due_invoice.amount_due -= amount_paid
                    due_invoice.amount_paid += amount_paid
                    
                    Payment.objects.create(
                        invoice=due_invoice,
                        amount_paid=amount_paid,
                        payment_method=invoice_data['payment_method'],
                        user=request.user
                    )
        
                    customer_account_balance.balance -= amount_paid
                    amount_paid = 0
                
                customer_account_balance.save()
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
                    subtotal=invoice_data['subtotal'],
                    note=invoice_data['note'],
                    products_purchased = ', '.join([f'{item['product_name']} x {item['quantity']}' for item in items_data])
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
                        quantity=item_data['quantity'],
                        unit_price=item.price,
                        invoice=invoice,
                        date=timezone.now()
                    )
                    
                    # stock log  
                    ActivityLog.objects.create(
                            branch=request.user.branch,
                            inventory=item,
                            user=request.user,
                            quantity=item_data['quantity'],
                            total_quantity = item.quantity,
                            action='Sale',
                            invoice=invoice
                        )
                    
                # # Create VATTransaction
                VATTransaction.objects.create(
                    invoice=invoice,
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
                    payment_method=invoice_data['payment_method'],
                    user=request.user
                )
                
                # updae account balance
                if invoice.payment_status == 'Partial':
                    customer_account_balance.balance += amount_due
                    customer_account_balance.save()
                    
                # Update customer balance
                account_balance.balance = Decimal(invoice_data['payable']) + Decimal(account_balance.balance)
                account_balance.save()
                
                # return redirect('finance:invoice_preview', invoice.id)
                return JsonResponse({'success':True, 'invoice_id': invoice.id})

        except (KeyError, json.JSONDecodeError, Customer.DoesNotExist, Inventory.DoesNotExist) as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return render(request, 'finance/invoices/add_invoice.html')


@login_required
@transaction.atomic
def delete_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    account = get_object_or_404(CustomerAccount, customer=invoice.customer)
    customer_account_balance = get_object_or_404(CustomerAccountBalances, account=account, currency=invoice.currency)

    sale = get_object_or_404(Sale, transaction=invoice)
    invoice_payment = get_object_or_404(Payment, invoice=invoice)
    stock_transactions = invoice.stocktransaction_set.all()  
    vat_transaction = get_object_or_404(VATTransaction, invoice=invoice)

    if invoice.payment_status == Invoice.PaymentStatus.PARTIAL:
        customer_account_balance.balance -= invoice.amount_due

    account_types = {
        'cash': Account.AccountType.CASH,
        'bank': Account.AccountType.BANK,
        'ecocash': Account.AccountType.ECOCASH,
    }

    account = get_object_or_404(
        Account, 
        name=f"{request.user.branch} {invoice.currency.name} {invoice_payment.payment_method.capitalize()} Account", 
        type=account_types.get(invoice_payment.payment_method, None)  # Handle case if payment_method is invalid
    )
    account_balance = get_object_or_404(AccountBalance, account=account, currency=invoice.currency, branch=request.user.branch)
    account_balance.balance -= invoice.amount_paid

    for stock_transaction in stock_transactions:
        product = Inventory.objects.get(product=stock_transaction.item, branch=request.user.branch)
        product.quantity += stock_transaction.quantity
        product.save()

        ActivityLog.objects.create(
            invoice=invoice,
            product_transfer=None,
            branch=request.user.branch,
            user=request.user,
            action='sale cancelled',
            inventory=product,
            quantity=stock_transaction.quantity,
            total_quantity=product.quantity
        )

    InvoiceItem.objects.filter(invoice=invoice).delete() 
    StockTransaction.objects.filter(invoice=invoice).delete()
    
    account_balance.save()
    customer_account_balance.save()
    sale.delete()
    vat_transaction.delete()
    invoice.delete()

    return JsonResponse({'message': f'Invoice {invoice.invoice_number} successfully deleted'})
    
    
    
@login_required       
def invoice_details(request, invoice_id):
    invoice = Invoice.objects.filter(id=invoice_id, branch=request.user.branch).values(
        'invoice_number',
        'customer__id', 
        'customer__name', 
        'products_purchased', 
        'payment_status', 
        'amount'
    )
    return JsonResponse(list(invoice), safe=False)


@login_required
def customer(request):
    if request.method == 'GET':
        customers = Customer.objects.all().values()
        return JsonResponse(list(customers), safe=False)
    
    elif request.method == 'POST':
        data = json.loads(request.body)

    

        if Customer.objects.filter(phone_number=data['phone_number']).exists():
            return JsonResponse({'success': False, 'message': 'Customer with this email already exists'})

        customer = Customer.objects.create(
            name=data['name'],
            email=data['email'],
            address=data['address'],
            phone_number=data['phonenumber']
        )
        account = CustomerAccount.objects.create(customer=customer)

        balances_to_create = [
            CustomerAccountBalances(account=account, currency=currency, balance=0) 
            for currency in Currency.objects.all()
        ]
        CustomerAccountBalances.objects.bulk_create(balances_to_create)

        return JsonResponse({'success': True, 'message': 'Customer successfully created'})

    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def customer_list(request):
    search_query = request.GET.get('q', '')
    
    customers = CustomerAccount.objects.all()
    
    if search_query:
        customers = CustomerAccount.objects.filter(Q(customer__name__icontains=search_query))
    
    if 'download' in request.GET:  
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=customers.xlsx'

        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        
        header_font = Font(bold=True)
        header_alignment = Alignment(horizontal='center')
        for col_num, header_title in enumerate(['Customer Name', 'Phone Number', 'Email', 'Account Balance'], start=1):
            cell = worksheet.cell(row=1, column=col_num)
            cell.value = header_title
            cell.font = header_font
            cell.alignment = header_alignment
            
            column_letter = openpyxl.utils.get_column_letter(col_num)
            worksheet.column_dimensions[column_letter].width = max(len(header_title), 20)

        customer_accounts = CustomerAccountBalances.objects.all()
        for customer in customer_accounts:
            worksheet.append(
                [customer.account.customer.name, 
                 customer.account.customer.phone_number, 
                 customer.account.customer.email, 
                 customer.balance if customer.balance else 0,
                ])  
            
        workbook.save(response)
        return response
        
    return render(request, 'finance/customers/customers.html', {'customers':customers, 'search_query':search_query})

@login_required
def update_customer(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)

    if request.method == 'POST':  
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, f'{customer.name} details updated successfully')  #
            return redirect('finance:customer_list')  
    else:
        form = CustomerForm(instance=customer)  

    return render(request, 'finance/customers/update_customer.html', {'form': form, 'customer': customer}) 

def delete_customer(request, customer_id):
    if request.method == 'DELETE':
        customer = get_object_or_404(Customer, pk=customer_id)

        customer_name = customer.name  
        customer.delete()
        messages.success(request, f'{customer_name} deleted successfully.')
        return JsonResponse({'status': 'success', 'message': f'Customer {customer_name} deleted successfully.'})  
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})  
    

@login_required
def customer_account(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)

    account = CustomerAccountBalances.objects.filter(account__customer=customer)

    invoices = Invoice.objects.filter(
        customer=customer, 
        branch=request.user.branch, 
        status=True
    )
    invoice_payments = Payment.objects.filter(
        invoice__branch=request.user.branch, 
        invoice__customer=customer
    ).order_by('-payment_date')

    filters = Q()
    if request.GET.get('q'):
        filters &= Q(payment_status=request.GET['q'])
    if request.GET.get('search_query'):
        search_query = request.GET['search_query']
        filters &= (Q(invoice_number__icontains=search_query) | Q(issue_date__icontains=search_query))

    invoices = invoices.filter(filters)

    if request.GET.get('email_bool'):
        html_string = render_to_string('finance/customers/email_temp.html', {
            "invoice_payments": invoice_payments, 
            "customer": customer, 
            'request': request
        })

        email = EmailMessage(
            'Your Account Statement',
            'Please find your invoice attached.',
            'your_email@example.com', 
            [customer.email],
        )

        with BytesIO() as buffer:
            pisa.CreatePDF(html_string, dest=buffer)
            buffer.seek(0)
            email.attach(f'account statement({customer.name}).pdf', buffer.getvalue(), 'application/pdf')

        email.send() 
        return JsonResponse({'message': 'Email sent'})

    return render(request, 'finance/customer.html', {
        'account': account,
        'invoices': invoices,
        'customer': customer,
        'invoice_count': invoices.count(),
        'invoice_payments': invoice_payments,
        'paid': invoices.filter(payment_status='Paid').count(),  
        'due': invoices.filter(payment_status='Partial').count(), 
    })


@login_required
def customer_account_transactions_json(request):
    customer_id = request.GET.get('customer_id')
    transaction_type = request.GET.get('type')

    customer = get_object_or_404(Customer, id=customer_id)  

    if transaction_type == 'invoices':
        invoices = Invoice.objects.filter(
            customer=customer, 
            branch=request.user.branch, 
            status=True
        ).order_by('-issue_date').values(
            'issue_date', 'invoice_number', 'products_purchased', 
            'amount_paid', 'amount_due', 'amount', 'user__username'
        )
        return JsonResponse(list(invoices), safe=False)
    else:
        return JsonResponse({'message': 'Invalid transaction type.'}, status=400)  

@login_required
def customer_account_payments_json(request):
    customer_id = request.GET.get('customer_id')
    transaction_type = request.GET.get('type')

    customer = get_object_or_404(Customer, id=customer_id)

    if transaction_type == 'invoice_payments':
        invoice_payments = Payment.objects.select_related('invoice', 'invoice__currency', 'user').filter(
            invoice__branch=request.user.branch, 
            invoice__customer=customer
        ).order_by('-payment_date').values(
            'payment_date', 'invoice__invoice_number', 'invoice__currency__symbol',
            'invoice__amount_due', 'invoice__amount', 'user__username', 'amount_paid'
        )
        return JsonResponse(list(invoice_payments), safe=False)
    else:
        return JsonResponse({'message': 'Invalid transaction type.'}, status=400)  


@login_required
def customer_account_json(request, customer_id):
    account = CustomerAccountBalances.objects.filter(account__customer__id=customer_id).values(
        'currency__symbol', 'balance'
    )   
    return JsonResponse(list(account), safe=False)
    
# currency views  
@login_required  
def currency(request):
    return render(request, 'finance/currency/currency.html')

@login_required
def currency_json(request):
    currency_id = request.GET.get('id', '')
    currency = Currency.objects.filter(id=currency_id).values()
    return JsonResponse(list(currency), safe=False)
 # Import your Currency model

@login_required
def add_currency(request):
    if request.method == 'POST':
        form = CurrencyForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Currency added successfully!')  
            except Exception as e: 
                messages.error(request, f'Error adding currency: {e}')
            return redirect('finance:currency') 
    else:
        form = CurrencyForm()

    return render(request, 'finance/currency/currency_add.html', {'form': form})


@login_required
def update_currency(request, currency_id):
    currency = get_object_or_404(Currency, id=currency_id)  

    if request.method == 'POST': 
        form = CurrencyForm(request.POST, instance=currency)  
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Currency updated successfully') 
            except Exception as e: 
                messages.error(request, f'Error updating currency: {e}')
            return redirect('finance:currency')  
    else:
        form = CurrencyForm(instance=currency) 

    return render(request, 'finance/currency/currency_add.html', {'form': form})

@login_required
def delete_currency(request, currency_id):
    from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404


@login_required
def delete_currency(request, currency_id):
    if request.method == 'POST': 
        currency = get_object_or_404(Currency, id=currency_id)
        
        try:
            if currency.invoice_set.exists() or currency.accountbalance_set.exists() or currency.expense_set.exists():  
                raise Exception("Currency is in use and cannot be deleted.")

            currency.delete()
            return JsonResponse({'message': 'Currency deleted successfully'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'message':'Deletion Failed'})


@login_required
def finance_settings(request):
    return render(request, 'finance/settings/settings.html')
    
# Reports
@login_required
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


@login_required 
def invoice_preview(request, invoice_id):
    invoice = Invoice.objects.get(id=invoice_id)
    invoice_items = InvoiceItem.objects.filter(invoice=invoice)
    account = CustomerAccount.objects.get(customer__id = invoice.customer.id)
    return render(request, 'Pos/printable_receipt.html', {'invoice_id':invoice_id, 'invoice':invoice, 'invoice_items':invoice_items})


@login_required
def invoice_preview_json(request, invoice_id):
    try:
        invoice = Invoice.objects.get(id=invoice_id)
    except Invoice.DoesNotExist:
        return JsonResponse({"error": "Invoice not found"}, status=404) 
     
    invoice_items = InvoiceItem.objects.filter(invoice=invoice).values(
        'item__product__name', 
        'quantity',
        'item__product__description',
        'total_amount'
    )

    invoice_dict = {
        field.name: getattr(invoice, field.name)
        for field in invoice._meta.fields
        if field.name not in ['customer', 'currency', 'branch', 'user']
    }

    # Add selected customer fields
    invoice_dict['customer_name'] = invoice.customer.name
    invoice_dict['customer_email'] = invoice.customer.email 
    invoice_dict['currency_symbol'] = invoice.currency.symbol
    
    if invoice.branch:
        invoice_dict['branch_name'] = invoice.branch.name
        invoice_dict['branch_phone'] = invoice.branch.phonenumber
        invoice_dict['branch_email'] = invoice.branch.email
        
    invoice_dict['user_username'] = invoice.user.username  
    
    invoice_data = {
        'invoice': invoice_dict,
        'invoice_items': list(invoice_items),
    }

    return JsonResponse(invoice_data)

@login_required
def invoice_pdf(request):
    template_name = 'finance/reports/invoice.html'
    invoice_id = request.GET.get('id', '')
    if invoice_id:
        try:
            invoice = get_object_or_404(Invoice, pk=invoice_id)

            invoice_items = InvoiceItem.objects.filter(invoice=invoice)
            
        except Invoice.DoesNotExist:
            return HttpResponse("Invoice not found")
    else:
        return HttpResponse("Invoice ID is required")
    
    return generate_pdf(
        template_name,
        {
            'title': 'Invoice', 
            'report_date': datetime.date.today(),
            'invoice':invoice,
            'invoice_items':invoice_items
        }
    )
    
# emails
@login_required
def send_invoice_email(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        invoice_id = data['invoice_id']
        invoice = Invoice.objects.get(id=invoice_id)
        invoice_items = InvoiceItem.objects.filter(invoice=invoice)
        account = CustomerAccount.objects.get(customer__id = invoice.customer.id)
        
        html_string = render_to_string('Pos/receipt.html', {'invoice': invoice, 'invoice_items':invoice_items, 'account':account})
        buffer = BytesIO()

        pisa.CreatePDF(html_string, dest=buffer) 

        email = EmailMessage(
            'Your Invoice',
            'Please find your invoice attached.',
            'your_email@example.com',
            ['recipient_email@example.com'],
        )
        
        buffer.seek(0)
        email.attach(f'invoice_{invoice.invoice_number}.pdf', buffer.getvalue(), 'application/pdf')

        # Send the email
        email.send()

        task = send_invoice_email_task.delay(data['invoice_id']) 
        task_id = task.id 
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename=invoice_{invoice.invoice_number}.pdf'
        
        return response
    return JsonResponse({'success': False, 'error':'error'})


#whatsapp
@login_required
def send_invoice_whatsapp(request, invoice_id):
    try:
        # Retrieve Invoice and Generate PDF
        invoice = Invoice.objects.get(pk=invoice_id)
        invoice_items = InvoiceItem.objects.filter(invoice=invoice)
        img = settings.STATIC_URL + "/assets/logo.png"
    
        html_string = render_to_string('Pos/invoice_template.html', {'invoice': invoice, 'request':request, 'invoice_items':invoice_items, 'img':img})
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(html_string, dest=pdf_buffer)
        if not pisa_status.err:
            # Save PDF to S3 and get URL
            s3 = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
            )
            invoice_filename = f"invoice_{invoice.invoice_number}.pdf"
            s3.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=f"invoices/{invoice_filename}",
                Body=pdf_buffer.getvalue(),
                ContentType="application/pdf",
                ACL="public-read",
            )
            s3_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/invoices/{invoice_filename}"

            # Send WhatsApp Message with Twilio
            account_sid = 'AC6890aa7c095ce1315c4a3a86f13bb403'
            auth_token = '897e02139a624574c5bd175aa7aaf628'
            client = Client(account_sid, auth_token)
            from_whatsapp_number = 'whatsapp:' + '+14155238886'
            to_whatsapp_number = 'whatsapp:' + '+263778587612'

            message = client.messages.create(
                from_=from_whatsapp_number,
                body="Your invoice is attached.",
                to=to_whatsapp_number,
                media_url=s3_url
            )
            logger.info(f"WhatsApp message SID: {message.sid}")
            return JsonResponse({"success": True, "message_sid": message.sid})
        else:
            logger.error(f"PDF generation error for Invoice ID: {invoice_id}")
            return JsonResponse({"error": "PDF generation failed"})
    except Invoice.DoesNotExist:
        logger.error(f"Invoice not found with ID: {invoice_id}")
        return JsonResponse({"error": "Invoice not found"})
    except Exception as e:
        logger.exception(f"Error sending invoice via WhatsApp: {e}")
        return JsonResponse({"error": "Error sending invoice via WhatsApp"})
    

# analytics
@login_required
def analytics(request):
    return render(request, 'finance/analytics/analytics.html')

@login_required
def end_of_day(request):
    today = timezone.now().date()
    
    sold_inventory = (
        StockTransaction.objects
        .filter(invoice__branch=request.user.branch, date=today, transaction_type=StockTransaction.TransactionType.SALE)
        .values('item__id', 'item__name')
        .annotate(quantity_sold=Sum('quantity'))
    )
    
    if request.method == 'GET':
        all_inventory = Inventory.objects.filter(branch=request.user.branch, status=True).values(
            'id', 'product__name', 'quantity'
        )

        inventory_data = []
        for item in sold_inventory:
            sold_info = next((inv for inv in all_inventory if item['item__id'] == inv['id']), None)
            
            if sold_info:
                inventory_data.append({
                    'id': item['item__id'],
                    'name': item['item__name'],
                    'initial_quantity': item['quantity_sold'] + sold_info['quantity'] if sold_info else 0,
                    'quantity_sold':  item['quantity_sold'],
                    'remaining_quantity':sold_info['quantity'] if sold_info else 0,
                    'physical_count': None
                })
           
        return JsonResponse({'inventory': inventory_data})
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            inventory_data = []
            
            for item in data:
                try:
                    inventory = Inventory.objects.get(id=item['item_id'], branch=request.user.branch, status=True)
                    inventory.physical_count = item['physical_count']
                    inventory.save()

                    sold_info = next((i for i in sold_inventory if i['item__id'] == inventory.id), None)
                    inventory_data.append({
                        'id': inventory.id,
                        'name': inventory.product.name,
                        'initial_quantity': inventory.quantity,
                        'quantity_sold': sold_info['quantity_sold'] if sold_info else 0,
                        'remaining_quantity': inventory.quantity - (sold_info['quantity_sold'] if sold_info else 0),
                        'physical_count': inventory.physical_count,
                        'difference': inventory.physical_count - (inventory.quantity - (sold_info['quantity_sold'] if sold_info else 0))
                    })
                except Inventory.DoesNotExist:
                    return JsonResponse({'success': False, 'error': f'Inventory item with id {item["item_id"]} does not exist.'})

            today_min = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_max = timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Invoice data
            invoices = Invoice.objects.filter(branch=request.user.branch, issue_date__range=(today_min, today_max))
            partial_invoices = invoices.filter(payment_status=Invoice.PaymentStatus.PARTIAL)
            paid_invoices = invoices.filter(payment_status=Invoice.PaymentStatus.PAID)
            
            # Expenses
            expenses = Expense.objects.filter(branch=request.user.branch, date=today)
            confirmed_expenses = expenses.filter(status=True)
            unconfirmed_expenses = expenses.filter(status=False)
            
            # Accounts
            account_balances = AccountBalance.objects.filter(branch=request.user.branch)

            html_string = render_to_string('day_report.html', {
                'request':request,
                'invoices':invoices,
                'expenses':expenses,
                'date': today,
                'inventory_data': inventory_data,
                'total_sales': paid_invoices.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0,
                'partial_payments': partial_invoices.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0,
                'total_paid_invoices': paid_invoices.count(),
                'total_partial_invoices': partial_invoices.count(),
                'total_expenses': confirmed_expenses.aggregate(Sum('amount'))['amount__sum'] or 0,
                'confirmed_expenses': confirmed_expenses,
                'unconfirmed_expenses': unconfirmed_expenses,
                'account_balances': account_balances,
            })
            
            pdf_buffer = BytesIO()
            pisa_status = pisa.CreatePDF(html_string, dest=pdf_buffer)
            if not pisa_status.err:
                # Save PDF to S3 and get URL
                s3 = boto3.client(
                    "s3",
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_S3_REGION_NAME,
                )
                invoice_filename = f"{request.user.branch.name}_today_report_{today}.pdf"
                s3.put_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Key=f"daily_reports/{invoice_filename}",
                    Body=pdf_buffer.getvalue(),
                    ContentType="application/pdf",
                    ACL="public-read",
                )
                s3_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/daily_reports/{invoice_filename}"

                # Send WhatsApp Message with Twilio
                
                account_sid = 'AC6890aa7c095ce1315c4a3a86f13bb403'
                auth_token = '897e02139a624574c5bd175aa7aaf628'
                client = Client(account_sid, auth_token)
                from_whatsapp_number = 'whatsapp:' + '+14155238886'
                to_whatsapp_number = 'whatsapp:' + '+263778587612'

                message = client.messages.create(
                    from_=from_whatsapp_number,
                    body="Today's report.",
                    to=to_whatsapp_number,
                    media_url=s3_url
                )

                logger.info(f"WhatsApp message SID: {message.sid}")
                return JsonResponse({"success": True, "message_sid": message.sid})
            else:
                return JsonResponse({"success": False, "error": "Error generating PDF."})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data.'})
        except Exception as e:
            logger.exception(f"Error processing request: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def invoice_payment_track(request):
    invoice_id = request.GET.get('invoice_id', '')
    
    if invoice_id:
        payments = Payment.objects.filter(invoice__id=invoice_id).order_by('-payment_date').values(
            'payment_date', 'amount_paid', 'payment_method', 'user__username'
        )
    return JsonResponse(list(payments), safe=False)



@login_required
def day_report(request, inventory_data):
    today_min = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_max = timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    
    # invoice data
    invoices = Invoice.objects.filter(branch=request.user.branch, issue_date__range=(today_min, today_max))
    
    partial_invoices = invoices.filter(payment_status=Invoice.PaymentStatus.PARTIAL)
    paid_invoices = invoices.filter(payment_status=Invoice.PaymentStatus.PAID)
    
    
    # expenses
    expenses = Expense.objects.filter(branch=request.user.branch, date=datetime.date.today())
    
    confirmed_expenses = expenses.filter(status=True)
    unconfirmed_expenses = expenses.filter(staus=False)
    
    # accounts
    account_balances = AccountBalance.objects.filter(branch=request.user.branch)
    
    try:
        html_string = render_to_string('day_report.html',{
                'request':request,
                'invoices':invoices,
                'date': datetime.date.today(),
                'inventory_data': inventory_data,
                'total_sales': paid_invoices.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0,
                'partial_payments': partial_invoices.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0,
                'total_paid_invoices': paid_invoices.count(),
                'expenses':expenses,
                'total_partial_invoices': partial_invoices.count(),
                'total_expenses': confirmed_expenses.aggregate(Sum('amount'))['amount__sum'] or 0,
                'confirmed_expenses': confirmed_expenses,
                'unconfirmed_expenses': unconfirmed_expenses,
                'account_balances': account_balances,
            })
        
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(html_string, dest=pdf_buffer)
        if not pisa_status.err:
            # Save PDF to S3 and get URL
            s3 = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
            )
            invoice_filename = f"{request.user.branch} today's ({datetime.date.today}) report.pdf"
            s3.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=f"daily_reports/{invoice_filename}",
                Body=pdf_buffer.getvalue(),
                ContentType="application/pdf",
                ACL="public-read",
            )
            s3_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/invoices/{invoice_filename}"

            # Send WhatsApp Message with Twilio
            account_sid = settings.TWILIO_ACCOUNT_SID
            auth_token = settings.TWILIO_AUTH_TOKEN
            client = Client(account_sid, auth_token)
            from_whatsapp_number = 'whatsapp:' + '+14155238886'
            to_whatsapp_number = 'whatsapp:' + '+263778587612'

            message = client.messages.create(
                from_=from_whatsapp_number,
                body="Today's report.",
                to=to_whatsapp_number,
                media_url=s3_url
            )

            logger.info(f"WhatsApp message SID: {message.sid}")
            return JsonResponse({"success": True, "message_sid": message.sid})
    except Exception as e:
        logger.exception(f"Error sending invoice via WhatsApp: {e}")
        return JsonResponse({"error": "Error sending invoice via WhatsApp"})

   
@login_required 
@transaction.atomic 
def cash_transfer(request):
    form = TransferForm()
    transfers = CashTransfers.objects.filter(branch=request.user.branch)
    
    account_types = {
        'cash': Account.AccountType.CASH,
        'bank': Account.AccountType.BANK,
        'ecocash': Account.AccountType.ECOCASH,
    }

    if request.method == 'POST':
        form = TransferForm(request.POST)
        
        if form.is_valid():
            transfer = form.save(commit=False)
            transfer.user = request.user
            transfer.notification_type = 'Expense'
            transfer.from_branch = request.user.branch
            transfer.branch = request.user.branch
            
            account_name = f"{request.user.branch} {transfer.currency.name} {transfer.transfer_method.capitalize()} Account"

            try:
                account = Account.objects.get(name=account_name, type=account_types[transfer.transfer_method.lower()])
            except Account.DoesNotExist:
                messages.error(request, f"Account '{account_name}' not found.")
                return redirect('finance:cash_transfer')  

            try:
                account_balance = AccountBalance.objects.select_for_update().get(
                    account=account,
                    currency=transfer.currency,
                    branch=request.user.branch
                )
            except AccountBalance.DoesNotExist:
                messages.error(request, "Account balance record not found.")
                return redirect('finance:cash_transfer')

            if account_balance.balance < transfer.amount:
                messages.error(request, "Insufficient funds in the account.")
                return redirect('finance:cash_transfer')  

            account_balance.balance -= transfer.amount
            account_balance.save()
            transfer.save()  
            

            # CashTransferConsumer.send_message({'message':'New cash transfer made!'})
            
            messages.success(request, 'Money successfully transferred.')
            return redirect('finance:cash_transfer')  
        else:
            messages.error(request, "Invalid form data. Please correct the errors.")
    return render(request, 'finance/transfers/cash_transfers.html', {'form': form, 'transfers':transfers})

@login_required
def finance_notifications_json(request):
    notifications = FinanceNotifications.objects.filter(status=True).values(
        'transfer__id', 
        'transfer__to',
        'expense__id',
        'expense__branch',
        'invoice__id',
        'invoice__branch',
        'notification',
        'notification_type',
        'id'
    )
    return JsonResponse(list(notifications), safe=False)


@login_required
@transaction.atomic
def cash_transfer_list(request):
    search_query = request.GET.get('q', '')
    transfers = CashTransfers.objects.filter(to=request.user.branch.id)
    
    if search_query:
        transfers = transfers.filter(Q(date__icontains=search_query))
        
    return render(request, 'finance/transfers/cash_transfers_list.html', {'transfers':transfers, 'search_query':search_query})

@login_required
@transaction.atomic
def receive_money_transfer(request, transfer_id):
    if transfer_id:
        transfer = get_object_or_404(CashTransfers, id=transfer_id)
        account_types = {
            'cash': Account.AccountType.CASH,
            'bank': Account.AccountType.BANK,
            'ecocash': Account.AccountType.ECOCASH,
        }
        
        account_name = f"{request.user.branch} {transfer.currency.name} {transfer.transfer_method.capitalize()} Account"

        try:
            account, _ = Account.objects.get_or_create(name=account_name, type=account_types[transfer.transfer_method.lower()])
        except Account.DoesNotExist:
            return JsonResponse({'message':f"Account '{account_name}' not found."}) 

        try:
            account_balance, _ = AccountBalance.objects.get_or_create(
                account=account,
                currency=transfer.currency,
                branch=request.user.branch
            )
        except AccountBalance.DoesNotExist:
            messages.error(request, )
            return JsonResponse({'message':"Account balance record not found."})  

        account_balance.balance += transfer.amount
        account_balance.save()
        
        transfer.received_status = True
        transfer.save() 
        return JsonResponse({'message':True})  
    return JsonResponse({'message':"Transfer ID is needed"})  


    
    
    
