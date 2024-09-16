from django.db import models


# A list of system notifications settings for a user.
class NotificationsSettings(models.Model):
    # products settings
    product_creation = models.BooleanField(default=True)
    product_update = models.BooleanField(default=True)
    product_deletion = models.BooleanField(default=True)
    invoice_on_sale = models.BooleanField(default=True)
    low_stock = models.BooleanField(default=False)

    service_creation = models.BooleanField(default=True)
    service_update = models.BooleanField(default=True)
    service_deletion = models.BooleanField(default=True)

    # transfers settings
    transfer_creation = models.BooleanField(default=True)
    transfer_approval = models.BooleanField(default=True)
    transfer_receiving = models.BooleanField(default=True)

    # finance settings
    expense_creation = models.BooleanField(default=True)
    expense_approval = models.BooleanField(default=True)
    recurring_invoices = models.BooleanField(default=True)
    money_transfer = models.BooleanField(default=True)
    cash_withdrawal = models.BooleanField(default=True)
    cash_deposits = models.BooleanField(default=True)

    # users settings
    user_creation = models.BooleanField(default=True)
    user_approval = models.BooleanField(default=True)
    user_deletion = models.BooleanField(default=True)
    user_login = models.BooleanField(default=True)

    user = models.ForeignKey("users.User", on_delete=models.CASCADE)

    def __str__(self):
        return self.user.email

# >>>>>>>>>>>>>>>>>>>>>> Remove unnecessary later>>>>>>>>>>>>>>>>>>

# class Printer(models.Model):
#     pc_identifier = models.CharField(max_length=255)
#     hostname = models.CharField(max_length=255)
#     name = models.CharField(max_length=100)
#     address = models.CharField(max_length=100)
#     printer_type = models.CharField(max_length=50, default='Bluetooth')
#
#     def __str__(self):
#         return f"{self.name} ({self.address}) for PC {self.pc_identifier} and Hostname {self.hostname}"


# Printer settings
# class Printer(models.Model):
#     """
#     The system uses 2 types of printers, bluetooth and system(locally configured) printers.
#     """
#     name = models.CharField(max_length=255)
#     ip_address = models.GenericIPAddressField()
#     pc_identifier = models.CharField(max_length=255)  # unique identifier of the pc
#     hostname = models.CharField(max_length=255)  # hostname of the pc
#     type = models.CharField(max_length=255, choices=(('bluetooth', 'Bluetooth'), ('system', 'System')))
#     is_default = models.BooleanField(default=False)
#     is_active = models.BooleanField(default=True)
#
#     def __str__(self):
#         return self.name


# Bluetooth printer settings
# class BluetoothPrinterSettings(Printer):
#     bluetooth_address = models.CharField(max_length=255, blank=True, null=True)
#     pairing_status = models.CharField(max_length=255)
#     pairing_code = models.CharField(max_length=255)
#
#     def __str__(self):
#         return self.name


# system printer settings
class Printer(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=100)
    printer_type = models.CharField(max_length=255, choices=(('bluetooth', 'Bluetooth'), ('system', 'System')))
    port = models.CharField(max_length=255)
    driver_name = models.CharField(max_length=255, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    pc_identifier = models.CharField(max_length=255)
    hostname = models.CharField(max_length=255, blank=True, null=True)
    mac_address = models.CharField(max_length=255, blank=True, null=True)
    system_uuid = models.CharField(max_length=255, blank=True, null=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
