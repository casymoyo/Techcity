from django.contrib import admin
from . models import *

admin.site.register(Transaction)
admin.site.register(StockTransaction)
admin.site.register(VATTransaction)
admin.site.register(VATRate)
admin.site.register(Customer)
admin.site.register(Expense)
admin.site.register(ExpenseCategory)
admin.site.register(Invoice)
admin.site.register(InvoiceItem)
admin.site.register(Sale)
admin.site.register(CustomerAccount)
admin.site.register(Currency)
admin.site.register(Payment)