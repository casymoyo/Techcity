from django.db import models


# A list of system notifications settings for a user.
class NotificationsSettings(models.Model):
    # products settings
    product_creation = models.BooleanField(default=True)
    product_update = models.BooleanField(default=True)
    product_deletion = models.BooleanField(default=True)
    service_creation = models.BooleanField(default=True)
    service_update = models.BooleanField(default=True)
    service_deletion = models.BooleanField(default=True)
    invoice_on_sale = models.BooleanField(default=True)

    # transfers settings
    transfer_creation = models.BooleanField(default=True)
    transfer_approval = models.BooleanField(default=True)

    # finance settings
    expense_creation = models.BooleanField(default=True)
    expense_approval = models.BooleanField(default=True)

    # users settings
    user_creation = models.BooleanField(default=True)
    user_approval = models.BooleanField(default=True)
    user_deletion = models.BooleanField(default=True)
    user_login = models.BooleanField(default=True)

    user = models.ForeignKey("users.User", on_delete=models.CASCADE)

    def __str__(self):
        return self.user.email
