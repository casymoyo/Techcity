from pickle import FALSE
import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

class PaymentMethod(models.Model):
    name = models.CharField(max_length=255)
    
    def __str__(self):
        return self.name
    
class Currency(models.Model):
    code = models.CharField(max_length=3, unique=True)  
    name = models.CharField(max_length=50)  
    symbol = models.CharField(max_length=5)  
    exchange_rate = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}"

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
    phone_number = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=100)
    id_number = models.CharField(max_length=100)
    date = models.DateField(auto_now_add=True)
    branch = models.ForeignKey('company.branch', on_delete=models.PROTECT)              
    
    def __str__(self):
        return self.name

class CustomerAccount(models.Model):
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE)
    
    def __str__(self):
        return f'{self.customer.name})'
    
class CustomerAccountBalances(models.Model):
    # Customer has two accounts i.e. USD and ZIG account
    account = models.ForeignKey(CustomerAccount, on_delete=models.CASCADE, related_name='balances')
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)  
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)   

    class Meta:
        unique_together = ('account', 'currency') 

    def __str__(self):
        return f'{self.account} - {self.currency}: {self.balance}'
    
class CustomerDeposits(models.Model):
    customer_account = models.ForeignKey("finance.CustomerAccountBalances", on_delete=models.CASCADE, related_name="customer_deposits")
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0) 
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)  
    payment_method = models.CharField(max_length=15, choices=[
        ('cash', 'cash'),
        ('bank', 'bank'),
        ('ecocash', 'ecocash')
    ]
    , default="cash")
    reason = models.CharField(max_length=255, null=False, blank=False)
    payment_reference = models.CharField(max_length=255, default="")
    cashier = models.ForeignKey("users.User", on_delete=models.DO_NOTHING, related_name="cashier")
    date_created = models.DateField(auto_now_add=True)
    branch = models.ForeignKey('company.branch', on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self) -> str:
        return f'{self.customer_account.account}'


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

    invoice = models.OneToOneField('finance.invoice', on_delete=models.CASCADE, null=True)
    purchase_order = models.OneToOneField('inventory.Purchaseorder', on_delete=models.CASCADE, null=True)
    vat_type = models.CharField(max_length=6, choices=VATType.choices)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2)
    paid = models.BooleanField(default=False)
    date = models.DateField(auto_now_add=True)
    
    def __str__(self):
        return f"VAT Transaction for {self.invoice}"

class Account(models.Model):

    class AccountType(models.TextChoices):
        CASH = 'CA', 'Cash'
        BANK = 'BA', 'Bank'
        ECOCASH = 'EC', 'Ecocash'
        
    name = models.CharField(max_length=50)
    type = models.CharField(
        max_length=2,
        choices=AccountType.choices,
        default=AccountType.CASH
    )
    
    def __str__(self):
        return f'{self.name} ({self.type})'
    
class AccountBalance(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='balances')
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    branch = models.ForeignKey('company.branch', on_delete=models.CASCADE)

    #class Meta:
    #    unique_together = ('account', 'currency')

    def __str__(self):
        return f'{self.account.name} ({self.account.type}):{self.currency}{self.balance}'


class StockTransaction(models.Model):
    class TransactionType(models.TextChoices):
        PURCHASE = 'Purchase', _('Purchase')
        SALE = 'Sale', _('Sale')
        ADJUSTMENT = 'Adjustment', _('Adjustment')

    item = models.ForeignKey('inventory.Product', on_delete=models.PROTECT)
    invoice = models.ForeignKey('finance.invoice', on_delete=models.PROTECT)
    transaction_type = models.CharField(max_length=10, choices=TransactionType.choices)
    payment_content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_stock_transactions')
    payment_object_id = models.PositiveIntegerField(null=True, blank=True)
    payment_object = GenericForeignKey('payment_content_type', 'payment_object_id') 

    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateField()

class ExpenseCategory(models.Model):
    name = models.CharField(max_length=50)
    
    def __str__(self):
        return self.name

class Expense(models.Model):
    issue_date = models.DateField(auto_now_add=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_method = models.CharField(max_length=15, choices=[
        ('cash', 'cash'),
        ('bank', 'bank'),
        ('ecocash', 'ecocash')
    ])
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT)
    description = models.CharField(max_length=200)
    user = models.ForeignKey('users.user', on_delete=models.CASCADE)
    branch = models.ForeignKey('company.branch', on_delete=models.CASCADE)
    status = models.BooleanField(default=False)
    purchase_order = models.ForeignKey("inventory.PurchaseOrder", on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"{self.issue_date} - {self.category} - {self.description} - ${self.amount}"
    
class Sale(models.Model):
    """
    Represents a sale transaction.
    """
    date = models.DateField()
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    transaction = models.ForeignKey('finance.Invoice', on_delete=models.PROTECT)
    

    def __str__(self):
        return f"Sale to {self.transaction.customer} on {self.date} ({self.total_amount})"

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
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)  
    issue_date = models.DateTimeField()
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0) 
    vat = models.DecimalField(max_digits=15, decimal_places=2, default=0)     
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)  
    amount_due = models.DecimalField(max_digits=15, decimal_places=2, default=0) 
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE, null=True) 
    payment_status = models.CharField(max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True)
    branch = models.ForeignKey('company.branch', on_delete=models.CASCADE)
    status = models.BooleanField(default=True)
    user = models.ForeignKey('users.User', on_delete=models.PROTECT, null=True)
    reocurring = models.BooleanField(default=False)
    subtotal =  models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    note = models.TextField(null=True)
    cancelled = models.BooleanField(default=False)
    products_purchased = models.TextField()
    invoice_return = models.BooleanField(default=False)
    payment_terms = models.CharField(choices=(
        ('cash', 'cash'),
        ('layby', 'layby'),
        ('installment', 'installment')
    ))
    hold_status = models.BooleanField(default=False)
    amount_received = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def generate_invoice_number(branch):
        last_invoice = Invoice.objects.filter(branch__name=branch).order_by('-id').first()
        if last_invoice:
            if str(last_invoice.invoice_number.split('-')[0])[-1] == branch[0]:
                last_invoice_number = int(last_invoice.invoice_number.split('-')[1]) 
                new_invoice_number = last_invoice_number + 1   
            else:
                new_invoice_number = 1
            return f"INV{branch[:1]}-{new_invoice_number:04d}"  
        else:
            new_invoice_number = 1
            return f"INV{branch[:1]}-{new_invoice_number:04d}"  

    def __str__(self):
        return f"Invoice #{self.invoice_number} - {self.customer}"

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='invoice_items')
    item = models.ForeignKey('inventory.Inventory', on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=15, decimal_places=2)
    vat_rate = models.ForeignKey(VATRate, on_delete=models.PROTECT)
    vat_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, editable=False)  
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    @property
    def subtotal(self):
        return Decimal(self.unit_price )* int(self.quantity)

    @property
    def total(self):
        return self.subtotal

    def save(self, *args, **kwargs):
        # Calculate and set the VAT amount automatically
        vat_rate_percentage = self.vat_rate.rate
        vat_rate = Decimal(vat_rate_percentage) / Decimal('100')  
        self.vat_amount = self.subtotal * vat_rate
        self.total_amount = self.total
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} x {self.item.product.description} for Invoice #{self.invoice.invoice_number}"
    

class layby(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='layby')

    def __str__(self):
        return f'{self.invoice}'

class laybyDates(models.Model):
    layby = models.ForeignKey(layby, on_delete=models.CASCADE)
    due_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f'{self.invoice}: {self.due_date}'
    
class recurringInvoices(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    status = models.BooleanField(default=False)
    
class Payment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount_due = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True) 
    # balance =  models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, choices=[
        ('cash', 'Cash'),
        ('credit card', 'Credit Card'),
        ('pay later', 'pay later'),
        ('Ecocash','Ecocash')
    ])
    user = models.ForeignKey('users.user', on_delete=models.PROTECT)
    
    def __str__(self):
        return f'{self.invoice.invoice_number} {self.amount_paid}'

class Cashbook(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, null=True)
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, null=True)
    issue_date = models.DateField(auto_now_add=True)
    description = models.CharField(max_length=255)
    debit = models.BooleanField(default=False)
    credit = models.BooleanField(default=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)
    branch = models.ForeignKey('company.branch', on_delete=models.CASCADE)
    manager = models.BooleanField(default=False)
    accountant = models.BooleanField(default=False, null=True)
    director = models.BooleanField(default=False, null=True)
    cancelled = models.BooleanField(default=False, null=True)
    note = models.TextField(default='', null=True)

    def __str__(self):
        return f'{self.issue_date}'

class CashBookNote(models.Model):
    entry = models.ForeignKey(Cashbook, related_name="notes", on_delete=models.CASCADE)
    user = models.ForeignKey('users.user', on_delete=models.CASCADE)
    note = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Note by {self.user.username} on {self.timestamp}"
    

class CashTransfers(models.Model):
    class TransferMethod(models.TextChoices):
        BANK = ('Bank'), _('Bank')
        CASH = ('Cash'), _('Cash')
        ECOCASH =('Ecocash'), _('Ecocash')
   
    date = models.DateField(auto_now_add=True)    
    from_branch = models.ForeignKey('company.Branch', on_delete=models.CASCADE, related_name='kwarikuenda')
    to = models.ForeignKey('company.Branch', on_delete=models.CASCADE, related_name='to')
    branch = models.ForeignKey('company.branch', on_delete=models.CASCADE, related_name='parent')
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)
    user = models.ForeignKey('users.User', on_delete=models.PROTECT)
    reason = models.CharField(max_length=255)
    transfer_method = models.CharField(max_length=10, choices=TransferMethod.choices, default=TransferMethod.CASH)
    received_status = models.BooleanField(default=False)
    
    def __str__(self):
        return f'{self.to}: {self.amount}'
    
class FinanceNotifications(models.Model):
    expense = models.OneToOneField(Expense, on_delete=models.CASCADE, null=True)
    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE, null=True)
    transfer = models.OneToOneField(CashTransfers, on_delete=models.CASCADE, null=True)
    notification = models.CharField(max_length=255)
    status = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    notification_type = models.CharField(max_length=20, choices=[
        ('Expense', 'Expense'),
        ('Invoice', 'Invoice'),
        ('Transfer', 'Transfer')
    ])

    def __str__(self):
        return self.notification
    
class Qoutation(models.Model):
    qoute_reference = models.CharField(max_length=255)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE, null=True) 
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.BooleanField(default=False)
    date = models.DateField(auto_now_add=True)
    branch = models.ForeignKey('company.branch', on_delete=models.CASCADE)
    products = models.CharField(max_length=255)
    
    def generate_qoute_number(branch):
        last_qoute = Qoutation.objects.filter(branch__name=branch).order_by('-id').first()
        if last_qoute:
            if str(last_qoute.qoute_reference.split('-')[0])[-1] == branch[0]:
                last_qoute_number = int(last_qoute.qoute_reference.split('-')[1]) 
                new_qoute_number = last_qoute_number + 1   
            else:
                new_qoute_number = 1
            return f"Q{branch[:1]}-{new_qoute_number :04d}"  
        else:
            new_qoute_number  = 1
            return f"Q{branch[:1]}-{new_qoute_number :04d}"  
    
    def __str__(self):
        return f'{self.qoute_reference} {self.customer.name}'
    
class QoutationItems(models.Model):
    qoute = models.ForeignKey(Qoutation, on_delete=models.CASCADE, related_name='qoute_items')
    product = models.ForeignKey('inventory.Inventory', on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    unit_price = models.DecimalField(max_digits=15, decimal_places=2)
    
    def __str__(self):
        return f'{self.qoute.qoute_reference} {self.product.product.name}'

class CashWithdraw(models.Model):
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    password = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    date = models.DateField(auto_now_add=True)
    time = models.TimeField(auto_now_add=True)
    status = models.BooleanField(default=False)
    reason = models.CharField(max_length=10)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)
    deleted = models.BooleanField(default=False)
    
    def __str__(self):
        return f'{self.date} {self.user.username} {self.amount}'
    
class PurchaseOrderAccount(models.Model):
    purchase_order = models.ForeignKey('inventory.PurchaseOrder', on_delete=models.CASCADE, related_name='purchase_order')
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    expensed = models.BooleanField(default=False)
    
    def __str__(self) -> str:
        return self.purchase_order.order_number

class PurchasesAccount(models.Model):
    purchase_order = models.ForeignKey('inventory.PurchaseOrder', on_delete=models.CASCADE, related_name='purchases')
    debit = models.BooleanField(default=False)
    credit = models.BooleanField(default=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

class COGS(models.Model):
    date = models.DateField(auto_now_add=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0) 

class COGSItems(models.Model):
    cogs = models.ForeignKey(COGS, on_delete=models.CASCADE, null=True)
    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE, null=True)
    product = models.ForeignKey('inventory.Inventory', on_delete=models.PROTECT)
    date = models.DateField(auto_now_add=True)


class SalesReturns(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    reason = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey("users.user", on_delete=models.CASCADE)
    
    def __str__(self) -> str:
        return self.invoice

class CashWithdrawals(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    timestamp = models.DateTimeField(auto_now=False, auto_now_add=False)
    description = models.CharField(max_length=255)
    user = models.ForeignKey("users.user", on_delete=models.CASCADE)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE) 

class CashDeposit(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    timestamp = models.DateTimeField(auto_now=False, auto_now_add=False)
    description = models.CharField(max_length=255)
    user = models.ForeignKey("users.user", on_delete=models.CASCADE)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE) 

    def __str__(self) -> str:
        return self.account.name 
    
class AccountTransaction(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, null=True)
    cash_withdrawal = models.ForeignKey(CashWithdraw, on_delete=models.CASCADE, null=True)
    cash_deposit = models.ForeignKey(CashDeposit, on_delete=models.CASCADE, null=True)
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, null=True)
    sales_returns = models.ForeignKey(SalesReturns, on_delete=models.CASCADE, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)