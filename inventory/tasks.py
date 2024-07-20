import threading
from . models import *
from utils.utils import send_mail_func
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

import logging
logger = logging.getLogger(__name__)

def send_stock_transfer_email(notification_id):
    notification = StockNotifications.objects.get(pk=notification_id)
    subject = 'Stock Transfer Notification'
    message = notification.notification
    from_email = 'admin@techcity.co.zw'
    to_email = 'cassymyo@gmail.com'
    email = EmailMessage(subject, message, from_email, [to_email])
    email.send()
    
def send_transfer_email(user_email, transfer_id, branch_id):
    # Validate inputs
    if not transfer_id or not branch_id or not user_email:
        logger.error("Invalid transfer_id or branch_id or user_email provided.")
        return
    
    try:
        transfer = Transfer.objects.get(id=transfer_id)
        
        try:
            branch = Branch.objects.get(id=branch_id)
        except Branch.DoesNotExist:
            logger.error(f"Branch with id {branch_id} does not exist.")
            return
        
        subject = 'Inventory transfer notification'
        message = f'''Hi, please take note Inventory with reference {transfer.transfer_ref} was transfered to your branch. 
                    Please also verify is the reference number on the IBT note is the same as on this email
                '''
        from_email = user_email
        to_email = [branch.email] 
        sender_name = transfer.user.first_name, transfer
        
        html_content = render_to_string('emails/email_template.html', {
            'subject': subject,
            'message': message,
            'sender_name': sender_name,
        })
        
        send_mail_func(subject, message, html_content, from_email, to_email)
        
        logger.info(f'Product transfer email to {branch.name} succefully sent')

    except Exception as e:
        logger.error(f"Error sending account statement email: {e}", exc_info=True)

