from django import forms
from . models import (
    Product,
    ProductCategory, 
    Inventory, Transfer, 
    DefectiveProduct, 
    Service, 
    Supplier, 
    PurchaseOrder,
    BatchCode, 
    reorderSettings
)
from datetime import date
from loguru import logger

class BatchForm(forms.ModelForm):
    class Meta:
        model = BatchCode
        fields = '__all__'

class AddProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'

class InventoryForm(forms.ModelForm):
    class Meta:
        model = Inventory
        exclude = ['branch', 'name']
        
class addCategoryForm(forms.ModelForm):
    class Meta:
        model = ProductCategory
        fields = '__all__'
        
class addTransferForm(forms.ModelForm):
    class Meta:
        model = Transfer
        exclude = ['transfer_ref', 'branch', 'user', 'quantity', 'defective_status', 'total_quantity_track']
        

class DefectiveForm(forms.ModelForm):
    class Meta:
        model = DefectiveProduct
        fields = ['id', 'quantity', 'reason', 'status', 'branch_loss']

class AddDefectiveForm(forms.ModelForm):
    class Meta:
        model = DefectiveProduct
        fields = ['product', 'quantity', 'reason', 'status',]

        
class RestockForm(forms.ModelForm):
    class Meta:
        model = DefectiveProduct
        fields = ['quantity']
        
class ServiceForm(forms.ModelForm):
    class Meta:
        model = Inventory
        fields = ['name', 'price']

class AddSupplierForm(forms.ModelForm):   
    class Meta :
        model = Supplier
        fields = '__all__'

class CreateOrderForm(forms.ModelForm):
    class Meta:
        model =  PurchaseOrder
        exclude = ['order_number', 'branch']
      

class noteStatusForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ['batch', 'status', 'delivery_date', 'payment_method', 'notes']
        
        widgets = {
            'delivery_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super(noteStatusForm, self).__init__(*args, **kwargs)
        
        if not self.initial.get('delivery_date'):
            self.initial['delivery_date'] = date.today()

        # set the batch incrementing from the previous
        if not self.initial.get('batch'):
            batch = PurchaseOrder.objects.filter().order_by('-order_date').first().batch
            if batch:
                batch_number = int(batch.split(' ')[1]) + 1
            else:
                batch_number = 1
            self.initial['batch'] = f'Batch {batch_number}'


class PurchaseOrderStatus(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ['status']

class ReorderSettingsForm(forms.ModelForm):
    class Meta:
        model = reorderSettings
        fields = ['supplier', 'quantity_suggestion', 'number_of_days_from', 'number_of_days_to', 'order_enough_stock']
       