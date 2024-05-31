from celery import shared_task
from datetime import datetime, timedelta

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from io import BytesIO
from xhtml2pdf import pisa 

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
        ['recipient_email@example.com'],
    )
    
    buffer.seek(0)
    email.attach(f'invoice_{invoice.invoice_number}.pdf', buffer.getvalue(), 'application/pdf')

    # Send the email
    email.send()
    print('done')

