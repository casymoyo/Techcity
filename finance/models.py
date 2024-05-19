import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

class Currency(models.Model):
    code = models.CharField(max_length=3, unique=True)  
    name = models.CharField(max_length=50)  
    symbol = models.CharField(max_length=5)  

    def __str__(self):
        return f"{self.code} - {self.name}"

class ChartOfAccounts(models.Model):
    class AccountType(models.TextChoices):
        ASSET = 'Asset', _('Asset')
        LIABILITY = 'Liability', _('Liability')
        EQUITY = 'Equity', _('Equity')
        REVENUE = 'Revenue', _('Revenue')
        EXPENSE = 'Expense', _('Expense')

    class NormalBalance(models.TextChoices):
        DEBIT = 'Debit', _('Debit')
        CREDIT = 'Credit', _('Credit')
        
    name = models.CharField(max_length=100)
    account_type = models.CharField(max_length=10, choices=AccountType.choices)
    normal_balance = models.CharField(max_length=6, choices=NormalBalance.choices)
    
    def __str__(self):
        return self.name

class Customer(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(blank=True)
    address = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name

class Transaction(models.Model):
    date = models.DateField()
    description = models.CharField(max_length=200, blank=True)
    account = models.ForeignKey(ChartOfAccounts, on_delete=models.PROTECT)
    debit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    reference_number = models.CharField(max_length=50, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    branch = models.ForeignKey('company.branch', on_delete=models.SET_NULL, null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.reference_number:  
            while True:  
                ref_number = uuid.uuid4().hex[:10].upper()  
                if not Transaction.objects.filter(reference_number=ref_number).exists():  
                    self.reference_number = ref_number
                    break  
        super(Transaction, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.date} - {self.description} - Ref: {self.reference_number}"

class VATRate(models.Model):
    rate = models.DecimalField(max_digits=5, decimal_places=2)
    description = models.CharField(max_length=50, blank=True)
    status = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.rate}% - {self.description}"

class VATTransaction(models.Model):
    class VATType(models.TextChoices):             
        INPUT = 'Input', _('Input')
        OUTPUT = 'Output', _('Output')

    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE)
    stock_transaction = models.OneToOneField('finance.StockTransaction', on_delete=models.CASCADE, null=True, blank=True)
    vat_type = models.CharField(max_length=6, choices=VATType.choices)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    def __str__(self):
        return f"VAT Transaction for {self.transaction} ({self.vat_type})"

class CashAccount(models.Model):
    name = models.CharField(max_length=50)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)

class BankAccount(models.Model):
    name = models.CharField(max_length=50)
    account_number = models.CharField(max_length=20)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)

class StockTransaction(models.Model):
    class TransactionType(models.TextChoices):
        PURCHASE = 'Purchase', _('Purchase')
        SALE = 'Sale', _('Sale')
        ADJUSTMENT = 'Adjustment', _('Adjustment')

    item = models.ForeignKey('inventory.Product', on_delete=models.PROTECT)
    transaction_type = models.CharField(max_length=10, choices=TransactionType.choices)
    payment_content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_stock_transactions')
    payment_object_id = models.PositiveIntegerField(null=True, blank=True)
    payment_object = GenericForeignKey('payment_content_type', 'payment_object_id') 

    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateField()

class ExpenseCategory(models.Model):
    name = models.CharField(max_length=50)
    
    def __str__(self):
        return self.name

class Expense(models.Model):
    date = models.DateField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT)
    description = models.CharField(max_length=200)
    branch = models.ForeignKey('company.branch', on_delete=models.CASCADE)


    def __str__(self):
        return f"{self.date} - {self.category} - {self.description} - ${self.amount}"

class PaymentMethod(models.Model):
    name = models.CharField(max_length=255)
    
    def __str__(self):
        return self.name
    
class Receipt(models.Model):
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE)  
    date = models.DateField()
    def __str__(self):
        return f"Receipt for Transaction #{self.transaction.pk} on {self.date.strftime('%Y-%m-%d')}" 


class ReceiptItem(models.Model):
    """
    Represents a line item on a sales receipt.
    """
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey('inventory.Inventory', on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.item.description} @ {self.unit_price} on Receipt #{self.receipt.pk}"


class Sale(models.Model):
    """
    Represents a sale transaction.
    """
    date = models.DateField()
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    transaction = models.ForeignKey('finance.Invoice', on_delete=models.PROTECT)
    

    def __str__(self):
        return f"Sale to {self.transaction.customer} on {self.date} ({self.total_amount})"


class PayLaterTransaction(models.Model):
    """
    Represents a pay later transaction.
    """
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE)
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Pay Later for {self.transaction} (due {self.due_date})"


class Invoice(models.Model):
    """
    Model representing an invoice.
    """
    class PaymentStatus(models.TextChoices):
        DRAFT = 'Draft', _('Draft')
        PENDING = 'Pending', _('Pending')
        PARTIAL = 'Partial', _('Partial')
        PAID = 'Paid', _('Paid')
        OVERDUE = 'Overdue', _('Overdue')

    invoice_number = models.CharField(max_length=50, unique=True)  
    # sale = models.ForeignKey(Sale, on_delete=models.CASCADE)         
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)  
    issue_date = models.DateField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0) 
    vat = models.DecimalField(max_digits=15, decimal_places=2, default=0)     
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)   
    payment_status = models.CharField(
        max_length=10, 
        choices=PaymentStatus.choices, 
        default=PaymentStatus.PENDING,
    )
    branch = models.ForeignKey('company.branch', on_delete=models.CASCADE)
    
    from django.db import models

    def generate_invoice_number():
        last_invoice = Invoice.objects.order_by('-id').first()
        if last_invoice:
            last_invoice_number = int(last_invoice.invoice_number.split('-')[1]) 
            new_invoice_number = last_invoice_number + 1
        else:
            new_invoice_number = 1
        current_year = timezone.now().year
        return f"INV{current_year}-{new_invoice_number:04d}"  

    def __str__(self):
        return f"Invoice #{self.invoice_number} - {self.customer}"

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='invoice_items')
    item = models.ForeignKey('inventory.Inventory', on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=15, decimal_places=2)
    # discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    vat_rate = models.ForeignKey(VATRate, on_delete=models.PROTECT)
    vat_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, editable=False)  

    # @property
    # def subtotal(self):
    #     discount_amount = self.unit_price * (self.discount_percentage / 100)
    #     return (self.unit_price - discount_amount) * self.quantity
    
    @property
    def subtotal(self):
        return Decimal(self.unit_price )* int(self.quantity)

    @property
    def total(self):
        return self.subtotal + self.vat_amount

    def save(self, *args, **kwargs):
        # Calculate and set the VAT amount automatically
        vat_rate_percentage = self.vat_rate.rate
        vat_rate = Decimal(vat_rate_percentage) / Decimal('100')  
        self.vat_amount = self.subtotal * vat_rate
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} x {self.item.product.description} for Invoice #{self.invoice.invoice_number}"