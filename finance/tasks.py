from celery import shared_task
from datetime import datetime, timedelta

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from io import BytesIO
from xhtml2pdf import pisa 
from django.utils import timezone
from django.conf import settings 

from finance.models import *

# @shared_task
# def generate_recurring_invoices():
#     two_days_ago = datetime.now() - timedelta(days=2)
#     invoices_due = Invoice.objects.filter(
#         recurring=True,  # Filter for recurring invoices
#         next_due_date__lte=two_days_ago  # Filter for invoices due 2 days ago or earlier
#     )

#     for invoice in invoices_due:
#         # Create a new invoice (copy or generate based on your logic)
#         new_invoice = Invoice(
#             # Copy relevant fields from the original invoice
#             customer=invoice.customer,
#             items=invoice.items,
#             # ... other fields
#             issue_date=datetime.now(),
#             due_date=datetime.now() + timedelta(days=invoice.payment_terms),
#             next_due_date=datetime.now() + timedelta(days=invoice.recurrence_period),
            
#             channel_layer = get_channel_layer()
#             async_to_sync(channel_layer.group_send)(
#             'invoice_notifications',  # Group name
#             {
#                 'type': 'invoice_created',
#                 'invoice': new_invoice.to_dict(),  # Serialize invoice data
#             }
#         )

#         )
#         new_invoice.save()

#         # Update the next_due_date of the original invoice
#         invoice.next_due_date += timedelta(days=invoice.recurrence_period)
#         invoice.save()


# # const webSocket = new WebSocket('ws://your-domain/ws/invoice-notifications/');

# # webSocket.onmessage = function(event) {
# #     const data = JSON.parse(event.data);
# #     if (data.type === 'invoice_created') {
# #         const invoice = data.invoice;
# #         // Display a notification to the user (e.g., using a toast library)
# #         alert("New Invoice Created: " + invoice.id); // Example alert
# #     }
# # };


@shared_task
def send_invoice_email_task(invoice_id):
    print(invoice_id)
    invoice = Invoice.objects.get(id=invoice_id)
    invoice_items = InvoiceItem.objects.filter(invoice=invoice)
    account = CustomerAccount.objects.get(customer__id = invoice.customer.id)
    
    html_string = render_to_string('pos/receipt.html', {'invoice': invoice, 'invoice_items':invoice_items, 'account':account})
    buffer = BytesIO()

    pisa.CreatePDF(html_string, dest=buffer) 

    email = EmailMessage(
        'Your Invoice',
        'Please find your invoice attached.',
        'your_email@example.com',
        ['cassymyto'],
    )
    
    buffer.seek(0)
    email.attach(f'invoice_{invoice.invoice_number}.pdf', buffer.getvalue(), 'application/pdf')

    # Send the email
    email.send()
    print('done')

@shared_task
def send_email_notification(notification_id):
    notification = FinanceNotifications.objects.get(pk=notification_id)
    subject = 'Cash Transfer Notification'
    message = notification.notification
    from_email = 'admin@techcity.co.zw'
    to_email = 'cassymyo@gmail.com'
    email = EmailMessage(subject, message, from_email, [to_email])
    email.send()

@shared_task
def send_expense_email_notification(expense_id):
    expense = Expense.objects.get(pk=expense_id)
    subject = 'Expense to be approved',
    message = expense.notification
    from_email = 'test@email.com'
    to_email = 'test@email.com'
    email = EmailMessage(subject, message, from_email, [to_email])
    email.send()
    
@shared_task
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
