from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from .models import ActivityLog, Inventory

# Connect the signal to the User model's save and delete methods
@receiver(post_save, sender=Inventory)  # Replace Inventory with the relevant model
def log_activity_on_save(sender, instance, created, **kwargs):
    if created:
        action = 'create'
    else:
        action = 'update'

    # Create an ActivityLog entry
    ActivityLog.objects.create(
        branch=instance.branch,
        inventory=instance.inventory,
        user=instance.user,
        action=action,
    )

@receiver(pre_delete, sender=Inventory)  # Replace Inventory with the relevant model
def log_activity_on_delete(sender, instance, **kwargs):
    # Create a log entry for deletion
    ActivityLog.objects.create(
        branch=instance.branch,
        inventory=instance.inventory,
        user=instance.user,
        action='delete',
    )