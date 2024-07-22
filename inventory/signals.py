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
    request = _request.request
    most_recent_stock_quantity = ActivityLog.objects.filter(inventory=instance).latest()
        
    logger.info(f'{most_recent_stock_quantity}: -> {most_recent_stock_quantity.total_quantity}')
    
    if int(instance.quantity) < int(instance.stock_level_threshold):
        if StockNotifications.objects.filter(inventory=instance).exists():
            if INVENTORY_EMAIL_NOTIFICATIONS_STATUS:
                send_low_stock_email(instance.id)
        else:
            StockNotifications.objects.create(
                inventory = instance,
                notification = f'{instance.product.name} stock level is now below stock threshold',
                status = True,
                type = 'stock level',
                quantity = most_recent_stock_quantity.total_quantity
            )
            if INVENTORY_EMAIL_NOTIFICATIONS_STATUS:
                send_low_stock_email(instance.id)
        
    else:
        notifications = StockNotifications.objects.filter(
            inventory=instance, 
            type='stock level', 
            inventory__branch=request.user.branch,
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
    
    

       
            