from django.urls import path
from . views import *
from . consumer import InventoryConsumer

app_name = 'inventory'

urlpatterns = [
    path('', inventory_index, name='inventory'),
    path('inventory/', inventory, name='inventory_list'),
    path('reorder/list', reoder_list, name='reoder_list'),
    path('product/list/', product_list, name='product_list'),
    path('add-product/', AddProductView.as_view(), name='add_product'),
    path('delete-inventory/', delete_inventory, name='delete_inventory'),
    path('notifications/', notifications_json, name='notifications_json'),
    path('add_category/', add_product_category, name='add_product_category'),
    path('inventory/branches/', branches_inventory, name='branches_inventory'),
    path('product/json/', inventory_index_json, name='inventory_index_json'),
    path('edit-inventory/<str:product_name>/', edit_inventory, name='edit_inventory'),
    path('defective_product_list/', defective_product_list, name='defective_product_list'),
    
    # transfers
    path('transfers', inventory_transfers, name='transfers'),
    path('over_less_list/', over_less_list_stock, name='over_less_list_stock'),
    path('delete/transfer/<int:transfer_id>/', delete_transfer, name='delete_transfer'),
    path('add/transfer/<str:transfer_ref>/', add_inventory_transfer, name='add_transfer'),
    path('receive-inventory', receive_inventory, name='receive_inventory'),
    path('inventory-detail/<int:id>/', inventory_detail, name='inventory_detail' ),
    path('transfer/detail/<int:transfer_id>/', transfer_details, name='transfer_details'),
    path('process-transfer-cart/', ProcessTransferCartView.as_view(), name='process_transfer_cart'),
    
    #reporting
    path('inventory-pdf', inventory_pdf, name='inventory_pdf'),
    path('transfers-report', transfers_report, name='transfers_report'),
    
    #websocket
    path('ws/inventory/<int:branchId>/',InventoryConsumer.as_asgi()),
]
