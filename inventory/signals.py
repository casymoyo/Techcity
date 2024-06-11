from django.dispatch import receiver
from .models import Inventory, StockNotifications, Transfer
from django.db.models.signals import post_save
from inventory.middleware import _request

@receiver(post_save, sender=Inventory)
def low_stock_notification(sender, instance, **kwargs):
    request = _request.request
    
    if instance.quantity < instance.stock_level_threshold:
        StockNotifications.objects.create(
            inventory = instance,
            notification = f'{instance.product.name} stock level is now below stock threshold',
            status = True,
            type = 'stock level' 
        )
    else:
        notifications = StockNotifications.objects.filter(
            inventory=instance, 
            type='stock level', 
            inventory__branch=request.user.branch,
            status=True
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

       
            