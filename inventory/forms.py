from django import forms
from . models import (
    Product,
    ProductCategory, 
    Inventory, Transfer, 
    DefectiveProduct, 
    Service, 
    Supplier, 
    PurchaseOrder
)

class AddProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'

class InventoryForm(forms.ModelForm):
    class Meta:
        model = Inventory
        exclude = ['branch']
        
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
        model = Service
        fields = '__all__'

class AddSupplierForm(forms.ModelForm):   
    class Meta :
        model = Supplier
        fields = '__all__'

class CreateOrderForm(forms.ModelForm):
    class Meta:
        model =  PurchaseOrder
        exclude = ['order_number', 'branch']
        