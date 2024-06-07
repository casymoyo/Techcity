import logging
from django.dispatch import receiver
from inventory.middleware import _request
from .tasks import send_email_notification
from django.db.models.signals import post_save
from .models import CashTransfers, FinanceNotifications, Expense, Invoice

logger = logging.getLogger(__name__)

@receiver(post_save, sender=CashTransfers)
def cash_transfer_notification(sender, instance, **kwargs):
    
    if instance.received_status == False:
        FinanceNotifications.objects.create(
            transfer=instance,
            notification=f'Receive {instance.currency.symbol} {instance.amount} send from {instance.from_branch}',
            status=True,
            notification_type='Transfer'
        )
        
        notification = FinanceNotifications.objects.get(pk=instance.id)
        send_email_notification.delay(notification)
    else:
        notification = FinanceNotifications.objects.get(
            transfer=instance, 
            status=True,
            notification_type='Expense'
        )
        
        notification.status=False
        notification.save()
        
@receiver(post_save, sender=Expense)
def expense_confirmation_notificatioin(sender, instance, **kwargs):
    if instance.status == False:
        send_email_notification.delay(instance.id)
        
        
@receiver(post_save, sender=Invoice)
def invoice_remove_notification(sender, instance, **kwargs):
    try:
        notification = FinanceNotifications.objects.get(
            invoice=instance,
            status=True,
            notification_type='Invoice'
        )
        
        notification.status=False
        notification.save()
    except FinanceNotifications.DoesNotExist:
        logger.warning(f"No active FinanceNotification found for Invoice #{instance.id}.")
    
    
     