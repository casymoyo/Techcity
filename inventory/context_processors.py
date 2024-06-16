from . models import ProductCategory, Inventory, StockNotifications

def product_category_list(request):
    return {'categories': ProductCategory.objects.all()}

def product_list(request):
    if request.user.id != None:
       return { 'inventory': Inventory.objects.filter(branch=request.user.branch)}
    return {}

def stock_notification_count(request):
    if request.user.id != None:
       return { 'notis_count': StockNotifications.objects.filter(
           type='stock level',
           status=True,
           inventory__branch=request.user.branch
        ).count()}
    return {}