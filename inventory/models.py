import random, string, uuid
from django.db import models
from company.models import Branch
from django.db.models import Sum
from django.utils import timezone
from django.db.models import F

class BatchCode(models.Model):
    code = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.code
    

class ProductCategory(models.Model):
    """Model for product categories."""

    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Product(models.Model):
    """Model for products."""

    tax_choices = [
        ('exempted', 'Exempted'),
        ('standard', 'Standard'),
        ('zero rated', 'Zero Rated')
    ]
    
    batch = models.CharField(max_length = 255, blank=True, default='')
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, default=0)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField(default=0, null=True)
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True)
    tax_type = models.CharField(max_length=50, choices=tax_choices)
    min_stock_level = models.IntegerField(default=0, null=True)
    description = models.TextField()
    end_of_day = models.BooleanField(default=False)
    service =  models.BooleanField(default=False)
    dealer_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, default=0)
    
    def __str__(self):
        return self.name

class Supplier(models.Model):
    """Model to represent suppliers."""
    name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()

    def __str__(self):
        return self.name

class PurchaseOrder(models.Model):
    """Model for purchase orders."""

    status_choices = [
        ('pending', 'Pending'),
        ('ordered', 'Ordered'),
        ('received', 'Received'),
        ('canceled', 'Canceled')
    ]

    order_number = models.CharField(max_length=100, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True)
    order_date = models.DateTimeField(default=timezone.now)
    delivery_date = models.DateField(null=True, blank=True)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    status = models.CharField(max_length=50, choices=status_choices, default='received')
    notes = models.CharField(max_length=255 ,null=True, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    discount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    other_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    is_partial = models.BooleanField(default=False)  
    received = models.BooleanField(default=False)
    payment_method = models.CharField(max_length=15, choices=[
        ('cash', 'cash'),
        ('bank', 'bank'),
        ('ecocash', 'ecocash')
    ]
    , default="cash")
    batch = models.CharField(max_length=20, null=True)
    hold = models.BooleanField(null=True, default=True)

    def generate_order_number():
        return f'PO-{uuid.uuid4().hex[:10].upper()}'

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super(PurchaseOrder, self).save(*args, **kwargs)

    def check_partial_status(self):
        partial_items = self.items.filter(received_quantity__lt=F('quantity'))
        self.is_partial = partial_items.exists()
        self.save()

    def __str__(self):
        return f"PO {self.order_number} - {self.supplier}"

class PurchaseOrderItem(models.Model):

    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.IntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    actual_unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    received_quantity = models.IntegerField(default=0) 
    received = models.BooleanField(default=False, null=True)
    expected_profit = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    dealer_expected_profit = models.DecimalField(max_digits=10, decimal_places=2, null=True)

    def receive_items(self, quantity):
       
        self.received_quantity += quantity
        if self.received_quantity >= self.quantity:
            self.received = True
        self.save()
        self.purchase_order.check_partial_status()  

    def check_received(self):
        """
        Checks if all related items in the purchase order with the same order_number are received and updates the purchase order's "received" flag.
        """
        order_number = self.purchase_order.order_number
        purchase_order_items = PurchaseOrderItem.objects.filter(purchase_order__order_number=order_number)

        all_received = True
        for item in purchase_order_items:
            if not item.received:
                all_received = False
            break

        purchase_order = PurchaseOrder.objects.get(order_number=order_number)
        purchase_order.received = all_received
        purchase_order.save()

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

class costAllocationPurchaseOrder(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE)
    allocated = models.DecimalField(max_digits=10, decimal_places=2)
    allocationRate = models.DecimalField(max_digits=10, decimal_places=2)
    expense_cost = models.DecimalField(max_digits=10, decimal_places=2)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField()
    product = models.CharField(max_length=255)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    total_buying = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self) -> str:
        return f'{self.purchase_order}: {self.product}'

class ProductDetail(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrderItem, on_delete=models.CASCADE) 

class otherExpenses(models.Model):

    """additional expenses for the purchase order"""

    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self) -> str:
        return f'{self.purchase_order} : {self.name} -> {self.amount}'

class Inventory(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=255, null=True)
    cost =  models.DecimalField(max_digits=10, decimal_places=2)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    dealer_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    quantity = models.IntegerField(null=True)
    status = models.BooleanField(default=True, null=True)
    stock_level_threshold = models.IntegerField(default=5, null=True)
    reorder = models.BooleanField(default=False, null=True)
    alert_notification = models.BooleanField(default=False, null=True, blank=True)
    batch = models.CharField(max_length=255, blank=True, null=True)
    
    def update_stock(self, added_quantity):
        self.quantity += added_quantity
        self.save()
    
    def __str__(self):
        return f'{self.branch.name} : ({self.product.name}) quantity ({self.quantity})'
    
class Transfer(models.Model):
    transfer_ref = models.CharField(max_length=20)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='user_branch')
    transfer_to = models.ForeignKey(Branch, on_delete=models.CASCADE)
    description =  models.CharField(max_length=266)
    date = models.DateField(auto_now_add=True)
    time = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    quantity =  models.IntegerField(default=0, null=True)
    total_quantity_track = models.IntegerField(default=0, null=True)
    defective_status = models.BooleanField(default=False)
    
    @classmethod
    def generate_transfer_ref(self, branch, destination_branch):
        last_transfer = Transfer.objects.filter(branch__name=branch).order_by('-id').first()
        if last_transfer:
            if str(last_transfer.transfer_ref.split(':')[0])[-1] == branch[0]:
                last_reference_number = int(last_transfer.transfer_ref.split('-')[1]) 
                new__reference_number = last_reference_number + 1   
            else:
                new__reference_number  = 1
            return f"{branch[:1]}:{destination_branch[:1]}-{new__reference_number:04d}"  
        else:
            new__reference_number = 1
            return f"{branch[:1]}:{destination_branch[:1]}-{new__reference_number:04d}"  
    
    
    def __str__(self):
        return self.transfer_ref

class TransferItems(models.Model):
    date = models.DateTimeField(auto_now_add=True)
    date_received = models.DateTimeField(auto_now_add=True)
    transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE)
    from_branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='destination')
    to_branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='source')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.IntegerField()
    over_less_quantity = models.IntegerField(null=True, default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    received = models.BooleanField(default=False)
    declined = models.BooleanField(default=False) 
    over_less = models.BooleanField(default=False)
    action_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, related_name='over_less_admin')
    quantity_track = models.IntegerField(default=0, null=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    over_less_description = models.CharField(max_length=255, null=True, blank=True)
    received_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    description = models.TextField()

    def __str__(self):
        return f'{self.product.name} to {self.to_branch}'

class DefectiveProduct(models.Model):
    product = models.ForeignKey(Inventory, on_delete=models.SET_NULL, null=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    date = models.DateField(auto_now_add=True)
    branch_loss = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='loss')
    reason = models.TextField()
    status = models.CharField(max_length=50, choices=[
        ('lost in transit','Lost in transit'),
        ('stolen', 'stolen'),
        ('damaged', 'Damage'),
    ])
    
    def __str__(self):
        return self.product.name

class ActivityLog(models.Model):
    """Model for activity logs."""

    ACTION_CHOICES = [
        ('stock in', 'stock in'),
        ('Stock update', 'Stock update'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('edit', 'Edit'),
        ('transfer', 'Transfer'),
        ('returns', 'returns'),
        ('sale', 'Sale'), 
        ('declined', 'Declined'),
        ('write off', 'write off'),
        ('defective', 'defective'),
        ('activated', 'activated'),
        ('deactivated', 'deactivated'),
        ('removed', 'removed')
    ]
    
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE) 
    user = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    quantity = models.IntegerField()
    total_quantity = models.IntegerField()
    timestamp = models.DateField(auto_now_add=True)
    description = models.CharField(max_length=255, null=True)
    purchase_order = models.ForeignKey(PurchaseOrder, null=True, blank=True, on_delete=models.SET_NULL)
    invoice = models.ForeignKey('finance.invoice', null=True, blank=True, on_delete=models.SET_NULL)
    product_transfer = models.ForeignKey(TransferItems, null=True, blank=True, on_delete=models.SET_NULL)
    
    class Meta:
        get_latest_by = 'timestamp'

    def __str__(self):
        return f"{self.user} ({self.timestamp})"
    
class StockNotifications(models.Model):
    inventory = models.ForeignKey(Inventory, null=True, blank=True, on_delete=models.SET_NULL)
    transfer = models.ForeignKey(Transfer, null=True, blank=True, on_delete=models.SET_NULL)
    notification = models.CharField(max_length=255)
    status = models.BooleanField(default=False)
    type = models.CharField(max_length=30, choices=[
        ('stock level', 'Stock level'),
        ('stock take', 'stock take'),
        ('stock transfer', 'stock transfer')
    ])
    quantity = models.IntegerField(blank=True, null=True, default=0)
    
    def __str__(self):
        return f'{self.inventory}: {self.notification}'
    
class ReorderList(models.Model):
    date = models.DateField(auto_now_add=True)
    product = models.ForeignKey(Inventory, on_delete=models.CASCADE)
    branch =  models.ForeignKey(Branch, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0 )
    
    def __str__(self):
        return f'{self.product.product.name}'

class ServiceCategory(models.Model):
    """Model for service categories."""
   
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class Service(models.Model):
    
    tax_choices = [
        ('exempted', 'Exempted'),
        ('standard', 'Standard'),
        ('zero rated', 'Zero Rated')
    ]
    
    name = models.CharField(max_length=255)
    cost =  models.DecimalField(max_digits=10, decimal_places=2)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_type = models.CharField(max_length=50, choices=tax_choices)
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True)
    description = models.TextField()
    
    def __str__(self):
        return self.name
    
class reorderSettings(models.Model):
    supplier = models.CharField(max_length=255)
    quantity_suggestion = models.BooleanField(default=False)
    number_of_days_from = models.FloatField(null=True)
    number_of_days_to = models.FloatField(null=True)
    order_enough_stock = models.BooleanField(default=False)
    date_created = models.DateField(auto_now_add=True)

    

