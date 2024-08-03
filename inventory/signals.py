import datetime
from django.dispatch import receiver
from django.db.models.signals import post_save
from inventory.middleware import _request
from .models import (
    Inventory, 
    StockNotifications, 
    Transfer, 
    TransferItems,
    ActivityLog
)

import logging
logger = logging.getLogger(__name__)

from .tasks import send_low_stock_email
from techcity.settings import INVENTORY_EMAIL_NOTIFICATIONS_STATUS


@receiver(post_save, sender=Inventory)
def low_stock_notification(sender, instance, **kwargs):
    request = _request.request if hasattr(_request, 'request') else None
    
    try:
        most_recent_stock_quantity = ActivityLog.objects.filter(inventory=instance).latest('timestamp')
        recent_quantity = most_recent_stock_quantity.total_quantity
    except ActivityLog.DoesNotExist:
        logger.warning(f"No ActivityLog entry found for Inventory ID {instance.id}")
        recent_quantity = 0

    logger.info(f'{instance.product.name}: Most recent quantity -> {recent_quantity}')
    
    if int(instance.quantity) < int(instance.stock_level_threshold):
       
        if StockNotifications.objects.filter(inventory=instance, type='stock level').exists():
            if INVENTORY_EMAIL_NOTIFICATIONS_STATUS:
                send_low_stock_email(instance.id)
        else:
            StockNotifications.objects.create(
                inventory=instance,
                notification=f'{instance.product.name} stock level is now below stock threshold',
                status=True,
                type='stock level',
                quantity=recent_quantity,
            )
            logger.info(f'notification created')
            if INVENTORY_EMAIL_NOTIFICATIONS_STATUS:
                send_low_stock_email(instance.id)
    else:
        
        notifications = StockNotifications.objects.filter(
            inventory=instance, 
            type='stock level', 
            status=True,
        )
        for notification in notifications:
            notification.status = False
            notification.save()


@receiver(post_save, sender=Transfer)
def stock_transfer_notification(sender, instance, **kwargs):
    StockNotifications.objects.create(
        transfer = instance,
        notification = f'Stock Transfer created yet to be received from {instance.transfer_to}',
        status = True,
        type = 'stock transfer' 
    )

@receiver(post_save, sender=TransferItems)
def track_quantity(sender, instance, **kwargs):
    transfer = Transfer.objects.get(id=instance.transfer.id)
    transfer.total_quantity_track += instance.quantity
    transfer.save()
    
    

       
            