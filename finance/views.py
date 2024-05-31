from .models import *
from decimal import Decimal
from io import BytesIO
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
from inventory.models import Inventory
import json, datetime, os, boto3, openpyxl 
from .tasks import send_invoice_email_task
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
from . forms import ExpenseForm, ExpenseCategoryForm, CurrencyForm, InvoiceForm, CustomerForm

import logging

logger = logging.getLogger(__name__)

class Finance(View):
    template_name = 'finance/finance.html'

    def get(self, request, *args, **kwargs):
        # Balances
        balances = AccountBalance.objects.all()
        print(balances)
        # Recent Transactions
        recent_transactions = Transaction.objects.all().order_by('-date')[:5]
       

        # 3. Expense Summary (Optional)
        expenses_by_category = Expense.objects.values('category__name').annotate(
            total_amount=Sum('amount', output_field=DecimalField())
        )
        
        context = {
            'balances': balances,
            'recent_transactions': recent_transactions,
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

@login_required
def confirm_expense(request, expense_id):
    expense = Expense.objects.get(id=expense_id)
    
    account_types = {
            'cash': Account.AccountType.CASH,
            'bank': Account.AccountType.BANK,
            'ecocash': Account.AccountType.ECOCASH,
        }

    account_name = f"{expense.currency.name} {expense.payment_method.capitalize()} Account"

    account = Account.objects.get(name=account_name, type=account_types[expense.payment_method])
    
    account_balance = AccountBalance.objects.get(account=account,  branch=request.user.branch)
    
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

@login_required       
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

@login_required
def update_invoice(request, invoice_id):
    form = InvoiceForm()
    invoice = Invoice.objects.get(id=invoice_id)
    account = CustomerAccount.objects.get(customer=invoice.customer)
    customer_account_balance = CustomerAccountBalances.objects.get(account=account, currency=invoice.currency)
    
    if request.method == 'GET':
        return render(request, 'finance/invoices/update_invoice.html', {'form':form, 'invoice':invoice})
    
    if request.method == 'POST':
        data = json.loads(request.body)
    
        amount_paid = Decimal(data['amount_paid'])
        
        if amount_paid < 0:
            return JsonResponse({'success':False, 'message':'Amount cant be below zero'})
        
        if Decimal(amount_paid) >= invoice.amount_due:
            invoice.payment_status=invoice.PaymentStatus.PAID
            invoice.amount_due = 0
        else:
            invoice.amount_due -= Decimal(amount_paid)
            
        invoice.amount_paid += Decimal(amount_paid)
            
        Payment.objects.create(
            invoice=invoice,
            amount_paid=Decimal(amount_paid),
            payment_method=data['payment_method']
        )
        
        account_types = {
            'cash': Account.AccountType.CASH,
            'bank': Account.AccountType.BANK,
            'ecocash': Account.AccountType.ECOCASH,
        }

        account_name = f"{invoice.currency.name} {data['payment_method'].capitalize()} Account"

        account = Account.objects.get(name=account_name, type=account_types[data['payment_method']])
        
        account_balance = AccountBalance.objects.get(account=account,  branch=request.user.branch)
        
        account_balance.balance += Decimal(amount_paid)
        
        customer_account_balance.balance -= Decimal(amount_paid)
        
        account_balance.save()
        customer_account_balance.save()
        invoice.save()
        
        return JsonResponse({'success':True, 'message':'Invoice Successfully Updated'})
    return JsonResponse({'success':False, 'message':'Update Failed'})

@login_required
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

            account_name = f"{currency.name} {invoice_data['payment_method'].capitalize()} Account"

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
            customer_account = customer_account_balance.account
            
            
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
                    
                else:
                    due_invoice.amount_due -= amount_paid
                    due_invoice.amount_paid += amount_paid
                    
                    Payment.objects.create(
                        invoice=due_invoice,
                        amount_paid=amount_paid,
                        payment_method='Cash'
                    )
        
                    customer_account_balance -= amount_paid
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
                    payment_method=invoice_data['payment_method']
                )
                
                # updae account balance
                if invoice.payment_status == 'Partial':
                    customer_account_balance.balance += amount_due
                    customer_account_balance.save()
                    
                # Update customer balance
                account_balance.balance = Decimal(invoice_data['payable']) + Decimal(account_balance.balance)
                account_balance.save()
                
                return redirect('finance:invoice_preview', invoice.id)

        except (KeyError, json.JSONDecodeError, Customer.DoesNotExist, Inventory.DoesNotExist) as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return render(request, 'finance/invoices/add_invoice.html')

@login_required
def customer(request):
    if request.method == 'GET':
        customers = Customer.objects.all().values()
        return JsonResponse(list(customers), safe=False)
    
    elif request.method == 'POST':
        data = json.loads(request.body)

        # Input Validation
        required_fields = ['name', 'email', 'address', 'phonenumber']
        if not all(data.get(field) for field in required_fields):
            return JsonResponse({'success': False, 'message': 'Missing required fields'})

        #Check if customer with the same email exists 
        if Customer.objects.filter(email=data['email']).exists():
            return JsonResponse({'success': False, 'message': 'Customer with this email already exists'})

        # Customer and Account Creation
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
            
            #Adjust column width to fit content
            column_letter = openpyxl.utils.get_column_letter(col_num)
            worksheet.column_dimensions[column_letter].width = max(len(header_title), 20)

        for customer in customers:
            worksheet.append([customer.customer.name, customer.customer.phone_number, customer.customer.email, customer.balance])  
            
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
    q = request.GET.get('q', '')
    search_query = request.GET.get('search_query', '')
    
    customer = Customer.objects.get(id=customer_id)
    account = CustomerAccountBalances.objects.filter(account__customer=customer)
    invoices = Invoice.objects.filter(customer=customer, branch=request.user.branch, status=True)
    
    if q:
        invoices = invoices.filter(payment_status=q)
    if search_query:
        invoices = invoices.filter(Q(invoice_number__icontains=search_query) | Q(issue_date__icontains=search_query) )

    
    return render(request, 'finance/customer.html', {
        'q':q,
        'account':account,
        'invoice_count':invoices.count(),
        'invoices':invoices,
        'customer':customer,
        'search_query':search_query,
        'paid':Invoice.objects.filter(payment_status='Paid', customer=customer, branch=request.user.branch, status=True).count(),
        'due':Invoice.objects.filter(payment_status='Partial', customer=customer, branch=request.user.branch, status=True).count(),
    })

# currency views  
@login_required  
def currency(request):
    return render(request, 'finance/currency/currency.html')

@login_required
def currency_json(request):
    currency_id = request.GET.get('id', '')
    currency = Currency.objects.filter(id=currency_id).values()
    return JsonResponse(list(currency), safe=False)

@login_required
def add_currency(request):
    form = CurrencyForm()
    if request.method == 'POST':
        form = CurrencyForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Currency successfully created')
            return redirect('finance:currency')
    return render(request, 'finance/currency/currency_add.html', {'form':form})

@login_required
def update_currency(request, currency_id):
    currency = get_object_or_404(Currency, id=currency_id)  

    if request.method == 'POST': 
        form = CurrencyForm(request.POST, instance=currency)  
        if form.is_valid():
            form.save()
            messages.success(request, 'Currency updated successfully')  
            return redirect('finance:currency')  
    else:
        form = CurrencyForm(instance=currency) 

    return render(request, 'finance/currency/currency_add.html', {'form': form})

@login_required
def delete_currency(request, currency_id):
    try:
        currency = Currency.objects.get(id=currency_id)
        currency.delete()
    except Currency.DoesNotExist:
        messages.error(request, 'Currency doesnt Exists')
        return JsonResponse({'message':'Currency doesnt exists'})
    return JsonResponse({'message':'Deleted Successfully'})

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
    return render(request, 'Pos/receipt.html', {'invoice_id':invoice_id, 'invoice':invoice, 'invoice_items':invoice_items})

@login_required
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
    
# email
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
            account_sid = settings.TWILIO_ACCOUNT_SID
            auth_token = settings.TWILIO_AUTH_TOKEN
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
    
    # Fetch sold inventory for today
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
        for inv in all_inventory:
            sold_info = next((item for item in sold_inventory if item['item__id'] == inv['id']), None)
            inventory_data.append({
                'id': inv['id'],
                'name': inv['product__name'],
                'initial_quantity': inv['quantity'],
                'quantity_sold': sold_info['quantity_sold'] if sold_info else 0,
                'remaining_quantity': inv['quantity'] - (sold_info['quantity_sold'] if sold_info else 0),
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
            else:
                return JsonResponse({"success": False, "error": "Error generating PDF."})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data.'})
        except Exception as e:
            logger.exception(f"Error processing request: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

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
    
    print(invoices)

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

   


    
    
    
    
    
