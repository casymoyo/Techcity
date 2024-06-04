import json, datetime
from . models import *
from decimal import Decimal
from django.views import View
from django.db.models import Q
from django.db import transaction
from django.contrib import messages
from utils.utils import generate_pdf
from django.http import JsonResponse
from asgiref.sync import async_to_sync
from finance.models import StockTransaction
from channels.layers import get_channel_layer 
from . utils import calculate_inventory_totals
from . forms import AddProductForm, addCategoryForm
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from channels.generic.websocket import  AsyncJsonWebsocketConsumer
from django.shortcuts import render, redirect, get_object_or_404, get_list_or_404
from permissions.permissions import admin_required, sales_required, accountant_required

@login_required
def notifications_json(request):
    notifications = StockNotifications.objects.filter(inventory__branch=request.user.branch).values(
        'inventory__product__name', 'type', 'notification', 'inventory__id'
    )
    return JsonResponse(list(notifications), safe=False)

@login_required
def product_list(request): 
    queryset = Inventory.objects.filter(branch=request.user.branch, status=True)
    search_query = request.GET.get('q', '') 
    product_id = request.GET.get('product', '')
    category_id = request.GET.get('category', '')

    if category_id:
        queryset = queryset.filter(product__category__id=category_id)
    if search_query:
        queryset = queryset.filter(
            Q(product__name__icontains=search_query) | 
            Q(product__description__icontains=search_query) 
        )
    if product_id:
        queryset = queryset.filter(id=product_id)

    inventory_data = list(queryset.values(
        'id', 'product__id', 'product__name', 'product__description', 'product__category__id', 'product__category__name',  'price', 'quantity'
    ))
    
    merged_data = [{
        'inventory_id': item['id'],
        'product_id': item['product__id'],
        'product_name':item['product__name'],
        'description': item['product__description'],
        'category': item['product__category__id'],
        'category_name': item['product__category__name'],
        'price': item['price'],
        'quantity': item['quantity'],
    } for item in inventory_data]

    return JsonResponse(merged_data, safe=False)

@login_required
def branches_inventory(request):
    search_query = request.GET.get('q', '')
    branch = request.GET.get('branches', '')
    category = request.GET.get('category', '')
    
    branches_inventory = Inventory.objects.filter(status=True)
    
    if search_query:
         branches_inventory = branches_inventory.filter(Q(product__name__icontains=search_query))
        
    if branch:
        branches_inventory = branches_inventory.filter(branch__id=branch)
        
    if category:
        if category == 'inactive':
            branches_inventory = branches_inventory.filter(status=False)
        else:
            branches_inventory = branches_inventory.filter(product__category__id=category)
    
    return render(request, 'inventory/branches_inventory.html', {
        'branches_inventory':branches_inventory,
        'branch':branch, 
        'search_query':search_query,
        'category':category
    })
        
class AddProductView(View):
    form_class = AddProductForm()
    initial = {'key':'value'}
    template_name = 'inventory/add_product.html'
    
    # @login_required
    def get(self, request, *args, **kwargs):
        form = self.form_class
        return render(request, self.template_name, {'form': form})
    
    # @login_required
    def post(self, request, *args, **kwargs):
        if request.method == 'POST':
            form = AddProductForm(request.POST)
            product_name = request.POST['name']
            
            try:
                product = Product.objects.get(name=product_name)
                
                product.quantity = int(request.POST['quantity'])
                product.price = Decimal(request.POST['price'])
                product.cost = Decimal(request.POST['cost'])
                product.save()

                message = 'Product successfully updated'
                log_action = 'Update'
            except Product.DoesNotExist:
                if form.is_valid():
                    product = form.save()
                    message = 'Product successfully created'
                    log_action = 'Create'
                else:
                    return redirect('inventory:inventory')
                
            self.create_branch_inventory(product, log_action)
            
            messages.success(request, message)
        return redirect('inventory:inventory')

    def create_branch_inventory(self, product, log_action):
        try:
            inv = Inventory.objects.get(product__name=product.name)
            inv.quantity += product.quantity
            inv.price = product.price
            inv.cost = product.cost
            inv.save()
            self.activity_log(log_action, inv, inv)
        except Inventory.DoesNotExist:
            inventory = Inventory.objects.create(
                product=product,
                quantity=product.quantity,
                price=product.price,
                cost=product.cost,
                branch=self.request.user.branch,
                stock_level_threshold=product.min_stock_level
            )
            self.activity_log(log_action, inventory, inv=0)  
    
    def activity_log(self, action, inventory, inv):
        ActivityLog.objects.create(
            branch = self.request.user.branch,
            user=self.request.user,
            action= action,
            inventory=inventory,
            quantity=inventory.quantity,
            total_quantity=inventory.quantity + inv.quantity if action == 'update' else inventory.quantity
        )

class ProcessTransferCartView(View):
    # @login_required
    def post(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                cart_data = json.loads(request.body)
                for item in cart_data:
                    transfer_item = Transfer(
                        product= Product.objects.get(name=item['product']),
                        price=item['price'],
                        quantity=item['quantity'],
                        from_branch= Branch.objects.get(name=item['from_branch']),
                        to_branch= Branch.objects.get(name=item['to_branch']),
                    )            
                    transfer_item.save()
                    self.deduct_inventory(item, transfer_item)  

            return JsonResponse({'success': 'Transfer success'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    def deduct_inventory(self, item, transfer_item):
        
        branch_inventory = Inventory.objects.get(product__name=item['product'], branch__name=item['from_branch'])
        
        branch_inventory.quantity -= int(item['quantity'])
        print(branch_inventory.quantity, int(item['quantity']))
        branch_inventory.save()
        print(branch_inventory.quantity)
        self.activity_log('Transfer', branch_inventory,  item, transfer_item, )
        
    # def send_stock_notification(self, item):
    #     print('here')
    #     channel_layer = get_channel_layer()
    #     async_to_sync(channel_layer.group_send)(
    #         f"branch_{item['to_branch']}",  
    #         {
    #             "type": "stock_transfer",
    #             "message": f'Stock transfer from {item['from_branch']} ',
    #         }
    #     )
    
    def activity_log(self,  action, inventory, item, transfer_item,):
        # print(transfer_item.id)
        ActivityLog.objects.create(
            invoice = None,
            product_transfer = transfer_item,
            branch = self.request.user.branch,
            user=self.request.user,
            action= action,
            inventory=inventory,
            quantity=item['quantity'],
            total_quantity=inventory.quantity
        )
        
@login_required       
def transfer_details(request, transfer_id):
    transfer = Transfer.objects.filter(id=transfer_id, from_branch=request.user.branch).values(
        'product__name', 'transfer_ref', 'quantity', 'price', 'from_branch__name', 'to_branch__name'
    )
    print(transfer)
    return JsonResponse(list(transfer), safe=False)

@login_required
def inventory(request):
    product_name = request.GET.get('name', '')
    if product_name:
        return JsonResponse(list(Inventory.objects.filter(product__name=product_name, branch=request.user.branch).values()), safe=False)
    return JsonResponse({'error':'product doesnt exists'})


@login_required
def inventory_index(request):
    """
    View for displaying inventory items and pending transfer notifications.
    """

    q = request.GET.get('q', '')  
    category = request.GET.get('category', '')
    
    inventory = Inventory.objects.filter(branch=request.user.branch, status=True)
    
    if category:
        
        if category == 'inactive':
            inventory = Inventory.objects.filter(branch=request.user.branch, status=False)
        else:
            inventory = inventory.filter(product__category__name=category)
        
    if q:
        inventory = inventory.filter(Q(product__name__icontains=q) | Q(product__batch_code__icontains=q))
    
    # Filter pending transfers
    pending_transfers = Transfer.objects.filter(
        to_branch=request.user.branch,
        received=False,
        declined=False
    )

    if request.user.branch.name == 'Warehouse':
        all_branches_inventory = Inventory.objects.all()
    else: all_branches_inventory = Inventory.objects.filter(branch=request.user.branch)
    
    totals = calculate_inventory_totals(all_branches_inventory.filter(status=True))
  
    return render(request, 'inventory/inventory.html', {
        'inventory': inventory,
        'search_query': q,
        'category':category,
        'total_price': totals[1],
        'total_cost':totals[0],
        'transfers_count': pending_transfers.count()
    })

@admin_required
@login_required
def edit_inventory(request, product_name):
        inv_product = Inventory.objects.get(product__name=product_name, branch=request.user.branch)
       
        if request.method == 'POST':
            product = Product.objects.get(name=product_name)
            product.name=request.POST['name']
            product.batch_code=request.POST['batch_code']
            product.description=request.POST['description']
            product.save()
            
            if inv_product.quantity < int(request.POST['quantity']):
                quantity = int(request.POST['quantity']) - inv_product.quantity
                inv_product.quantity += quantity
                action = 'Stock in'
                
            elif inv_product.quantity > int(request.POST['quantity']):
                quantity = inv_product.quantity - int(request.POST['quantity']) 
                inv_product.quantity += quantity
                action = 'Update'
            
            else:
                quantity = inv_product.quantity 
                action = 'Edit'
                
            inv_product.price = Decimal(request.POST['price'])
            inv_product.cost = Decimal(request.POST['cost'])
                
            inv_product.save()
            
            ActivityLog.objects.create(
                branch = request.user.branch,
                user=request.user,
                action= action,
                inventory=inv_product,
                quantity=quantity,
                total_quantity=inv_product.quantity,
            )
            
            messages.success(request, f'{product.name} update succesfully')
            return redirect('inventory:inventory')
        return render(request, 'inventory/inventory_form.html', {'product':inv_product})

@login_required
def inventory_detail(request, id):
    """Inventory detail view."""
    
    q = request.GET.get('q', '')

    inventory = Inventory.objects.get(id=id, branch=request.user.branch)
    
    logs = ActivityLog.objects.filter(inventory=inventory, branch=request.user.branch)
    stock_transactions = StockTransaction()
    

    logs_filter = ActivityLog.objects.filter(
        Q(timestamp__icontains=q) |
        Q(user__username__icontains=q)
    ) & ActivityLog.objects.filter(inventory=inventory, branch=request.user.branch)
    
    return render(request, 'inventory/inventory_detail.html', {
        'inventory':inventory,
        'logs':logs_filter if logs_filter.exists() else logs ,
        'search_query':q
    })


@login_required    
def inventory_transfers(request):
    """
    View for displaying inventory transfers, optionally filtered by search query.
    """

    q = request.GET.get('q', '') 
    branch_id = request.GET.get('branch', '')

    transfers = Transfer.objects.filter(from_branch=request.user.branch).order_by('-date')
    
    if q:
        transfers = transfers.filter(Q(product__name__icontains=q) | Q(date__icontains=q) )
        
    if branch_id: 
        transfers =transfers.filter(to_branch__id=branch_id)

    return render(request, 'inventory/transfers.html', {'transfers': transfers,'search_query': q })
    
    
@login_required
def receive_inventory(request):
    q = request.GET.get('q', '')
    
    transfers =  Transfer.objects.filter(
        to_branch=request.user.branch,
        received=False,
        declined=False
    )
    
    if q:
        transfers = transfers.filter(
            Q(product__name__icontains=q) |
            Q(date__icontains=q) 
        ) 
    
    if request.method == 'POST':
        transfer_id = request.POST.get('id')  

        try:
            branch_transfer = get_object_or_404(transfers, id=transfer_id)

            if request.POST['received'] == 'true':
                    if Inventory.objects.filter(product=branch_transfer.product, branch=request.user.branch).exists():
                        existing_inventory = Inventory.objects.get(product=branch_transfer.product, branch=request.user.branch)
                        existing_inventory.quantity += branch_transfer.quantity
                        existing_inventory.price = branch_transfer.price
                        existing_inventory.save()
                        
                        branch_transfer.received = True
                        ActivityLog.objects.create(
                            branch = request.user.branch,
                            user=request.user,
                            action= 'Update',
                            inventory=existing_inventory,
                            quantity=branch_transfer.quantity,
                            total_quantity=existing_inventory.quantity
                        )
                        messages.success(request, 'Product received')
                        
                    else:
                        inventory = Inventory.objects.create(
                            branch=request.user.branch,
                            product=branch_transfer.product,
                            cost=branch_transfer.product.cost,  
                            price=branch_transfer.price,
                            quantity=branch_transfer.quantity
                        )
                        branch_transfer.received = True
                        ActivityLog.objects.create(
                            branch = request.user.branch,
                            user=request.user,
                            action= 'Create',
                            inventory=inventory,
                            quantity=inventory.quantity,
                            total_quantity=inventory.quantity
                        )
                        messages.success(request, 'Product received')
            else:
                try:
                    declined_product = Inventory.objects.get(product=branch_transfer.product, branch=branch_transfer.from_branch)
                    
                    declined_product.quantity += branch_transfer.quantity
                    declined_product.save()
                    
                    branch_transfer.declined = True
                    ActivityLog.objects.create(
                            branch = request.user.branch,
                            user=request.user,
                            action= 'Decline',
                            inventory=declined_product,
                            quantity=branch_transfer.quantity,
                            total_quantity=declined_product.quantity
                        )
                    messages.success(request, 'Product declined')
                except:
                    messages.warning(request, 'Request failed')

            branch_transfer.save()
            return redirect('inventory:receive_inventory')  

        except Transfer.DoesNotExist:
            messages.error(request, 'Invalid transfer ID')
        except Exception: 
            messages.error(request, 'Error in processing the request')

    return render(request, 'inventory/receive_inventory.html', {'transfers': transfers})


@login_required
def add_inventory_transfer(request):
    return render(request, 'inventory/add_transfer.html')

@login_required
@admin_required
def delete_inventory(request):
    """Deletes an inventory item. """
    
    product_id = request.GET.get('product_id')
    inv = Inventory.objects.get(id=product_id, branch=request.user.branch)
    inv.status = False
    inv.save()
    
    ActivityLog.objects.create(
            branch = request.user.branch,
            user=request.user,
            action= 'Delete',
            inventory=inv,
            quantity=inv.quantity,
            total_quantity=inv.quantity
        )
    
    messages.success(request, 'Product successfully deleted')
    return redirect('inventory:inventory')

@login_required
@admin_required
def add_product_category(request):
    categories = ProductCategory.objects.all().values()
    
    if request.method == 'POST':
        data = json.loads(request.body)
        category_name = data['name']
        
        if ProductCategory.objects.filter(name=category_name).exists():
            return JsonResponse({'error', 'Category Exists'})
        
        ProductCategory.objects.create(
            name=category_name
        )
    return JsonResponse(list(categories), safe=False)       

# reports
@login_required
def inventory_pdf(request):
    """Generates a PDF report of inventory items, optionally filtered by category."""
    
    template_name = 'inventory/reports/inventory_pdf.html'
    category = request.GET.get('category', '')

    inventory = get_list_or_404(Inventory, branch=request.user.branch.id, product__category__name=category) if category else get_list_or_404(Inventory, branch=request.user.branch.id)
    title = f'{category} Inventory' if category else 'All Inventory'
    
    totals = calculate_inventory_totals(inventory)
    
    return generate_pdf(
        template_name, {
            'inventory':inventory,
            'title': f'{request.user.branch.name}: {title}',
            'date':datetime.date.today(),
            'total_cost':totals[0],
            'total_price':totals[1],
            'pdf_name':'Inventory'
        }
    )

@login_required
def transfers_report(request):
    """Generates a PDF report of expenses based on filtered transfers."""
    
    template_name = 'inventory/reports/transfers.html'
    product_id = request.GET.get('product', '')
    branch_id = request.GET.get('branch', '')
    end_date_str = request.GET.get('date_from', '') 
    start_date_str = request.GET.get('date_to', '')
    view = request.GET.get('view', '')
    
    
    if start_date_str or end_date_str: 
        try:
            end_date = datetime.date.fromisoformat(end_date_str)
            start_date = datetime.date.fromisoformat(start_date_str)
        except ValueError:
            messages.error(request, 'Invalid date format. Please use YYYY-MM-DD.')
    else:
        start_date = ''
        end_date = ''
        
    try:
        product_id = int(product_id) if product_id else None
        branch_id = int(branch_id) if branch_id else None
    except ValueError:
        return JsonResponse({'messages':'Invalid product or branch ID.'})

    transfers = Transfer.objects.filter()  

    if product_id:
        transfers = transfers.filter(product__id=product_id)
    if branch_id:
        transfers = transfers.filter(to_branch_id=branch_id)
    if start_date and end_date:
        transfers = transfers.filter(date__range=(start_date, end_date))
        
    if view:
        return JsonResponse(list(transfers.order_by('-date').values(
                'date', 
                'product__name', 
                'quantity', 
                'from_branch__name',
                'to_branch__name',
                'received',
                'declined'
            )), 
            safe=False
        )
    
    return generate_pdf(
        template_name,
        {
            'title': 'Transfers', 
            'date_range': f"{start_date} to {end_date}", 
            'report_date': datetime.date.today(),
            'transfers':transfers
        },
    )
    