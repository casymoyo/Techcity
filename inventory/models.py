from django.db import models
from company.models import Branch


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

    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=0, null=True)
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True)
    tax_type = models.CharField(max_length=50, choices=tax_choices)
    description = models.TextField()
    
    def __str__(self):
        return self.name

class Inventory(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    cost =  models.DecimalField(max_digits=10, decimal_places=2)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    status = models.BooleanField(default=True)
    
    def __str__(self):
        return f'{self.branch.name} : ({self.product.name}) quantity ({self.quantity})'
    
class Transfer(models.Model):
    from_branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='destination')
    to_branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='source')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(auto_now_add=True)
    received = models.BooleanField(default=False)
    declined = models.BooleanField(default=False)

    def __str__(self):
        return self.product.name

class DefectiveProduct(models.Model):
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
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
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('edit', 'Edit'),
        ('transfer', 'Transfer'),
        ('returns', 'Returns'),
        ('sale', 'Sale'), 
        ('declined', 'Declined')
    ]
    
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE) 
    user = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    quantity = models.PositiveIntegerField()
    total_quantity = models.PositiveIntegerField()
    timestamp = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} ({self.timestamp})"

class CartItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    branch_from = models.ForeignKey('company.Branch', on_delete=models.CASCADE, related_name='from_branch')
    branch_to = models.ForeignKey('company.Branch', on_delete=models.CASCADE, related_name='to_branch')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    
    def __str__(self):
        return self.product
    
