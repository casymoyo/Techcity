from celery import shared_task
from finance.models import Invoice

# @shared_task
# # def send_receipt_email(invoice_id):
# #     # Get the invoice and relevant data
# #     invoice = Invoice.objects.get(pk=invoice_id)
# #     # ... your logic to generate the receipt PDF

# #     send_mail(
# #         subject='Your Receipt',
# #         message='Thank you for your purchase!',
# #         from_email='your_email@example.com',
# #         recipient_list=[invoice.customer.email],
# #         fail_silently=False,
# #         attachments=[('receipt.pdf', pdf_content, 'application/pdf')] 
# #     )

@shared_task
def add(x, y):
    return x + y
