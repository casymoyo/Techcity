import logging
import datetime
from datetime import timedelta
from django.db.models import Max
from django.dispatch import receiver
from inventory.middleware import _request
from .tasks import send_email_notification
from django.db.models.signals import post_save
from .models import CashTransfers, FinanceNotifications, Expense, Invoice, Cashbook

from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)

@receiver(post_save, sender=CashTransfers)
def cash_transfer_notification(sender, instance, **kwargs):
    
    if instance.received_status==False:
        FinanceNotifications.objects.create(
            transfer=instance,
            notification=f'Receive {instance.currency.symbol} {instance.amount} send from {instance.from_branch}',
            status=True,
            notification_type='Transfer'
        )
        
        notification = FinanceNotifications.objects.get(transfer=instance)
        notification = FinanceNotifications.objects.get(pk=notification.id)
        # subject = 'Cash Transfer Notification'
        # message = notification.notification
        # from_email = 'admin@techcity.co.zw'
        # to_email = 'cassymyo@gmail.com'
        # email = EmailMessage(subject, message, from_email, [to_email])
        # email.send()
        send_email_notification.delay(notification.id)
    elif instance.received_status==True:
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
        pass
        
        
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

def create_cashbook_entry(instance, debit, credit):
    if instance.cancelled or instance.invoice_return:
        Cashbook.objects.create(
                issue_date=instance.issue_date,
                description=f'Sales returns ({instance.instance.invoice_number})',
                debit=credit,
                credit=debit,
                amount=instance.amount_paid,
                currency=instance.currency
            )
    else:
        if instance.amount_paid != 0:
            Cashbook.objects.create(
                issue_date=instance.issue_date,
                description=f'Sale of {instance.products_purchased}({instance.invoice_number})' if instance.amount_paid == instance.amount else f' Sale update for {instance.products_purchased}({instance.invoice_number})',
                debit=debit,
                credit=credit,
                amount=instance.amount_paid,
                currency=instance.currency
            )

@receiver(post_save, sender=Invoice)
def create_invoice_cashbook_entry(sender, instance, **kwargs):
    create_cashbook_entry(instance, debit=True, credit=False)

@receiver(post_save, sender=Expense)
def create_expense_cashbook_entry(sender, instance, **kwargs):
    if instance.status == True:
        create_cashbook_entry(instance, instance.description, debit=False, credit=True)

@receiver(post_save, sender=CashTransfers)
def create_cash_transfer_cashbook_entry(sender, instance, **kwargs):
    create_cashbook_entry(instance, f'Cash Transfer of {instance.amount} from {instance.from_branch.name}', debit=True, credit=False)

