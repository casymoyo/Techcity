from django import forms
from . models import Product, ProductCategory, Inventory, Transfer, DefectiveProduct

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
        exclude = ['transfer_ref', 'branch']
        

class DefectiveForm(forms.ModelForm):
    class Meta:
        model = DefectiveProduct
        fields = ['id','reason', 'status']
        

class RestockForm(forms.ModelForm):
    class Meta:
        model = DefectiveProduct
        fields = ['quantity']