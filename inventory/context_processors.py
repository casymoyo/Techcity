from . models import ProductCategory, Inventory
from django.contrib.auth.decorators import login_required


def product_category_list(request):
    return {'categories': ProductCategory.objects.all()}


def product_list(request):
    if request.user.id != None:
       return { 'inventory': Inventory.objects.filter(branch=request.user.branch)}
    return {}