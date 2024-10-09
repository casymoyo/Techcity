from django.urls import path
from . views import *
from . consumer import InventoryConsumer

app_name = 'inventory'

urlpatterns = [
    path('', inventory_index, name='inventory'),
    path('inventory/', inventory, name='inventory_list'),
    path('product/list/', product_list, name='product_list'),
    path('add-product/', AddProductView.as_view(), name='add_product'),
    path('delete-inventory/', delete_inventory, name='delete_inventory'),
    path('notifications/', notifications_json, name='notifications_json'),
    path('add_category/', add_product_category, name='add_product_category'),
    path('inventory/branches/', branches_inventory, name='branches_inventory'),
    path('product/json/', inventory_index_json, name='inventory_index_json'),
    path('edit/<str:product_name>/', edit_inventory, name='edit_inventory'),
    path('activate/product/<int:product_id>/', activate_inventory, name='activate_inventory'),
    path('defective_product_list/', defective_product_list, name='defective_product_list'),
    path('inventory/branches/json', branches_inventory_json, name='branches_inventory_json'),

    #batch_code 
    path('batch_code/', batch_code, name='batch_code'),
    
    # product
    path('create/product/', product, name='product'),
    
    # supplier
    path('suppliers/list', suppliers, name='suppliers'),
    path('edit/supplier/', edit_supplier, name='edit_supplier'),
    path('create/supplier/', create_supplier, name='create_supplier'),
    path('supplier/json/list/', supplier_list_json, name='supplier_list_json'),
    
    # defective
    path('add/defective/product/', create_defective_product, name='create_defective_product'),
    
    # services
    path('create/service/', service, name='create_service'),
    path('edit/service/<int:service_id>/', edit_service, name='edit_service'),
    
    # re-oder
    path('reorder/list', reorder_list, name='reorder_list'),
    path('create/order/list/', create_order_list, name='create_order_list'),
    path('reorder/list/json', reorder_list_json, name='reorder_list_json'),
    path('clear/reorder/list/', clear_reorder_list, name='clear_reorder_list'),
    path('reorder/from/notifications/', reorder_from_notifications, name='reorder_from_notifications'),
    path('add/reoder/quantity', add_reorder_quantity, name='add_reoder_quantity'),
    path('settings/', reorder_settings, name='reorder_settings'),
    
    # purchase_order
    path('purchase_orders/list/', purchase_orders, name='purchase_orders'),
    path('print/purchase_order/<int:order_id>/', print_purchase_order, name='print_purchase_order'),
    path('purchase_order/create/', create_purchase_order, name='create_purchase_order'),
    path('purchase_order/receive/<int:order_id>/', receive_order, name='receive_order'),
    path('process/purchase_order/', process_received_order, name='process_received_order'),
    path('purchase_order/detail/<int:order_id>/', purchase_order_detail, name='purchase_order_detail'),
    path('purchase_order/delete/<int:purchase_order_id>/', delete_purchase_order, name='delete_purchase_order'),
    path('purchase_orders/status/<int:order_id>/', change_purchase_order_status, name='change_purchase_order_status'),
    
    # transfers
    path('transfers', inventory_transfers, name='transfers'),
    path('print/transfer/<int:transfer_id>/', print_transfer, name='print_transfer'),
    path('receive/transfer/', receive_inventory, name='receive_inventory'),
    path('receive/transfer/json/', receive_inventory_json, name='receive_inventory_json'),
    path('over_less_list/', over_less_list_stock, name='over_less_list_stock'),
    path('delete/transfer/<int:transfer_id>/', delete_transfer, name='delete_transfer'),
    path('add/transfer/', add_inventory_transfer, name='add_transfer'),
    path('detail/<int:id>/', inventory_detail, name='inventory_detail' ),
    path('transfer/detail/<int:transfer_id>/', transfer_details, name='transfer_details'),
    path('process-transfer-cart/', ProcessTransferCartView.as_view(), name='process_transfer_cart'),
    
    #reporting
    path('inventory-pdf', inventory_pdf, name='inventory_pdf'),
    path('transfers-report', transfers_report, name='transfers_report'),
    
    #websocket
    path('ws/inventory/<int:branchId>/',InventoryConsumer.as_asgi()),
]
