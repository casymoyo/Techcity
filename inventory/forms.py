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
        exclude = ['transfer_ref', 'branch', 'user', 'quantity', 'defective_status', 'total_quantity_track']
        

class DefectiveForm(forms.ModelForm):
    class Meta:
        model = DefectiveProduct
        fields = ['id','reason', 'status', 'branch_loss']

class AddDefectiveForm(forms.ModelForm):
    class Meta:
        model = DefectiveProduct
        fields = ['product', 'reason', 'status']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  
        super().__init__(*args, **kwargs)
        if user:
            self.fields['product'].queryset = Product.objects.filter(branch=user.branch)

        
class RestockForm(forms.ModelForm):
    class Meta:
        model = DefectiveProduct
        fields = ['quantity']