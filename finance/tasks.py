import threading
from datetime import datetime, timedelta
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from io import BytesIO
from xhtml2pdf import pisa 
from django.utils import timezone
from django.conf import settings 

from finance.models import *
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from utils.utils import send_mail_func

def all_invoices():
    print(Invoice.objects.all())

def generate_recurring_invoices():
    two_days_ago = datetime.now() - timedelta(days=2)
    invoices_due = Invoice.objects.filter(
        recurring=True,  # Filter for recurring invoices
        next_due_date__lte=two_days_ago  # Filter for invoices due 2 days ago or earlier
    )

    for invoice in invoices_due:
        # Create a new invoice (copy or generate based on your logic)
        new_invoice = Invoice(
            # Copy relevant fields from the original invoice
            customer=invoice.customer,
            items=invoice.items,
            # ... other fields
            issue_date=datetime.now(),
            due_date=datetime.now() + timedelta(days=invoice.payment_terms),
            next_due_date=datetime.now() + timedelta(days=invoice.recurrence_period), 
        )
        new_invoice.save()

        # Update the next_due_date of the original invoice
        invoice.next_due_date += timedelta(days=invoice.recurrence_period)
        invoice.save()




def send_invoice_email_task(invoice_id):
    invoice = Invoice.objects.get(id=invoice_id)
    invoice_items = InvoiceItem.objects.filter(invoice=invoice)
    account = CustomerAccount.objects.get(customer__id = invoice.customer.id)
    
    html_string = render_to_string('pos/receipt.html', {'invoice': invoice, 'invoice_items':invoice_items, 'account':account})
    buffer = BytesIO()

    pisa.CreatePDF(html_string, dest=buffer) 

    # email = EmailMessage(
    #     'Your Invoice',
    #     'Please find your invoice attached.',
    #     'cassymyo@gmail.com',
    #     ['cassymyo@gmail.com'],
    # )
    send_html_mail(
        'Your Invoice',
        'Please find your invoice attached.',
        'cassymyo@gmail.com',
        ['cassymyo@gmail.com'],
    )
    
    # buffer.seek(0)
    # email.attach(f'invoice_{invoice.invoice_number}.pdf', buffer.getvalue(), 'application/pdf')

    # # Send the email
    # email.send()
    print('done')



def send_email_notification(notification_id):
    try:
        expense = Expense.objects.get(pk=notification_id)
        
        subject = 'Expense Confirmation Notification'
        message = f'Please log on to confirm the expense: {expense.description}'
        from_email = expense.user.email
        to_email = ['cassymyo@gmail.com']  #to change
        sender_name = expense.user.first_name

        # Render the email template with context
        html_content = render_to_string('emails/email_template.html', {
            'subject': subject,
            'message': message,
            'sender_name': sender_name,
        })

        send_mail_func(subject, message, html_content, from_email, to_email)
            
    except Expense.DoesNotExist:
        print(f"Expense with ID {notification_id} does not exist")

    except Exception as e:
        print(f"An error occurred while sending email: {e}")



def send_expense_email_notification(expense_id):
    expense = Expense.objects.get(pk=expense_id)
    subject = 'Expense to be approved',
    message = expense.notification
    from_email = 'test@email.com'
    to_email = 'test@email.com'
    email = EmailMessage(subject, message, from_email, [to_email])
    email.send()

def check_and_send_invoice_reminders():
    timezone.activate(settings.TIME_ZONE) 
    now = timezone.now()
    
    due_invoices = Invoice.objects.filter(due_date__lte=now.date(), payment_status=Invoice.PaymentStatus.PARTIAL)  

    for invoice in due_invoices:
        days_overdue = (now.date() - invoice.due_date).days

        # Internal Notification
        internal_subject = f"Invoice #{invoice.id} Overdue by {days_overdue} Days"
        internal_message = (
            f"Invoice #{invoice.id} for {invoice.customer.name} is {days_overdue} days overdue. Payment status: Partial"
        )
        internal_recipients = ["your-team@example.com"]  
        
        email = EmailMessage(
            internal_subject, internal_message, "from@example.com", internal_recipients
        )
        email.send()
        
        FinanceNotifications.objects.create(
            invoice=Invoice,
            notificatioin=f"Invoice #{invoice.id} for {invoice.customer.name} is {days_overdue} days overdue. Payment status: Partial",
            status=False,
            notification_type='Invoice'
        )

        # Customer Notification
        customer_subject = f"Overdue Invoice Reminder (Invoice #{invoice.id})"
        customer_message = f"Dear {invoice.customer.name},\n\nThis is a reminder that your invoice #{invoice.id} was due on {invoice.due_date} and is currently {days_overdue} days overdue. Please settle the remaining balance as soon as possible.\n\nThank you,\nYour Company"
        email = EmailMessage(
            customer_subject, customer_message, "from@example.com", [invoice.customer.email]
        )
        email.send()
