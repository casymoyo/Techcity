from . models import *
from celery import shared_task
from django.core.mail import EmailMessage
from django.template.loader import render_to_string


@shared_task
def send_stock_transfer_email(notification_id):
    notification = StockNotifications.objects.get(pk=notification_id)
    subject = 'Stock Transfer Notification'
    message = notification.notification
    from_email = 'admin@techcity.co.zw'
    to_email = 'cassymyo@gmail.com'
    email = EmailMessage(subject, message, from_email, [to_email])
    email.send()
