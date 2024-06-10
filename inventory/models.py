import random, string
from django.db import models
from company.models import Branch
from django.db.utils import IntegrityError


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
    batch_code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField(default=0, null=True)
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True)
    tax_type = models.CharField(max_length=50, choices=tax_choices)
    min_stock_level = models.IntegerField(default=0, null=True)
    description = models.TextField()
    
    def __str__(self):
        return self.name

class Inventory(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    cost =  models.DecimalField(max_digits=10, decimal_places=2)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField()
    status = models.BooleanField(default=True)
    stock_level_threshold = models.IntegerField(default=5)
    
    def __str__(self):
        return f'{self.branch.name} : ({self.product.name}) quantity ({self.quantity})'
    
class Transfer(models.Model):
    transfer_ref = models.CharField(max_length=20)
    from_branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='destination')
    to_branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='source')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(auto_now_add=True)
    received = models.BooleanField(default=False)
    declined = models.BooleanField(default=False)
    
    @classmethod
    def generate_transfer_number(cls):
        while True:
            characters = string.ascii_uppercase + string.digits  
            transfer_ref = ''.join(random.choices(characters, k=6))  
            if not cls.objects.filter(transfer_ref=transfer_ref).exists():
                return transfer_ref

    def save(self, *args, **kwargs):
        if not self.transfer_ref:
            self.transfer_ref = self.generate_transfer_number()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.product.name
    

class DefectiveProduct(models.Model):
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    date = models.DateField(auto_now_add=True)
    reason = models.TextField()
    status = models.CharField(max_length=50, choices=[
        ('pending','Pending'),
        ('repaired', 'Repaired'),
        ('replaced', 'Replaced'),
        ('scrapped', 'Scrapped')
    ])
    
    def __str__(self):
        return self.product.name

class ActivityLog(models.Model):
    """Model for activity logs."""

    ACTION_CHOICES = [
        ('stock in', 'Stock in'),
        ('Stock update', 'Stock update'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('edit', 'Edit'),
        ('transfer', 'Transfer'),
        ('returns', 'Returns'),
        ('sale', 'Sale'), 
        ('declined', 'Declined'),
    ]
    
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE) 
    user = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    quantity = models.IntegerField()
    total_quantity = models.IntegerField()
    timestamp = models.DateField(auto_now_add=True)
    invoice = models.ForeignKey('finance.invoice', null=True, blank=True, on_delete=models.SET_NULL)
    product_transfer = models.ForeignKey(Transfer, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.user} ({self.timestamp})"
    
class StockNotifications(models.Model):
    inventory = models.ForeignKey(Inventory, on_delete=models.PROTECT)
    notification = models.CharField(max_length=255)
    status = models.BooleanField(default=False)
    type = models.CharField(max_length=30, choices=[
        ('stock level', 'Stock level'),
        ('stock take', 'stock take')
    ])
    
    def __str__(self):
        return f'{self.inventory.product.name}: {self.notification}'



    
