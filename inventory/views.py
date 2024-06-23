import json, datetime, openpyxl 
from openpyxl.styles import Alignment, Font, PatternFill
from . models import *
from decimal import Decimal
from django.views import View
from django.db.models import Q
from django.db.models import Sum
from django.db import transaction
from django.contrib import messages
from utils.utils import generate_pdf
from django.http import JsonResponse, HttpResponse
from asgiref.sync import async_to_sync
from finance.models import StockTransaction
from channels.layers import get_channel_layer 
from . utils import calculate_inventory_totals
from . forms import AddProductForm, addCategoryForm, addTransferForm, DefectiveForm, RestockForm
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
                    log_action = 'stock in'
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
                transfer=Transfer.objects.get(id=cart_data['transfer_id'])
                for item in cart_data['cart']:
                    transfer_item = TransferItems(
                        transfer=transfer,
                        product= Product.objects.get(name=item['product']),
                        price=item['price'],
                        quantity=item['quantity'],
                        from_branch= Branch.objects.get(name=item['from_branch']),
                        to_branch= Branch.objects.get(name=item['to_branch']),
                    )            
                    transfer_item.save()
                    print(transfer_item)
                    self.deduct_inventory(item, transfer_item)  

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    def deduct_inventory(self, item, transfer_item):
        
        branch_inventory = Inventory.objects.get(product__name=item['product'], branch__name=item['from_branch'])
        
        branch_inventory.quantity -= int(item['quantity'])
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
def delete_transfer(request, transfer_id):
    transfer = get_object_or_404(Transfer, id=transfer_id)

    transfer.delete()
    
    return JsonResponse({'success':True})
        
@login_required       
def transfer_details(request, transfer_id):
    transfer = TransferItems.objects.filter(id=transfer_id).values(
        'product__name', 'transfer__transfer_ref', 'quantity', 'price', 'from_branch__name', 'to_branch__name'
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
    q = request.GET.get('q', '')  
    category = request.GET.get('category', '')    
    product_id = request.GET.get('product_id','')    
    
    inventory = Inventory.objects.filter(branch=request.user.branch, status=True).order_by('product__name')

    if product_id:
        product = get_object_or_404(Inventory, product__id=product_id, branch=request.user.branch)
        ReoderList.objects.create(
            product=product
        )
        product.reorder = True
        product.save()
        
        messages.success(request, 'Product succefully added to re-oder list')
        return redirect('inventory:inventory')
    
    if category:
        
        if category == 'inactive':
            inventory = Inventory.objects.filter(branch=request.user.branch, status=False)
        else:
            inventory = inventory.filter(product__category__id=category)
        
    if q:
        inventory = inventory.filter(Q(product__name__icontains=q) | Q(product__batch_code__icontains=q))
        
    
    if 'download' and 'excel' in request.GET:
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename={request.user.branch.name} stock.xlsx'
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        
        # Add products data
        products = Inventory.objects.all()
        branches = Branch.objects.all().values_list('name', flat=True).distinct()
        row_offset = 0
        for branch in branches:
            worksheet['A' + str(row_offset + 1)] = f'{branch} Products'
            worksheet.merge_cells('A' + str(row_offset + 1) + ':D' + str(row_offset + 1))
            cell = worksheet['A' + str(row_offset + 1)]
            cell.alignment = Alignment(horizontal='center')
            cell.font = Font(size=16, bold=True)
            cell.fill = PatternFill(fgColor='AAAAAA', fill_type='solid')

            row_offset += 1 
            
            category_headers = ['Name', 'Cost', 'Price', 'Quantity']
            for col_num, header_title in enumerate(category_headers, start=1):
                cell = worksheet.cell(row=3, column=col_num)
                cell.value = header_title
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal='center')

            categories = Inventory.objects.filter(branch=request.user.branch).values_list('product__category__name', flat=True).distinct()
            for category in categories:
                products_in_category = products.filter(branch__name=branch, product__category__name=category)
                if products_in_category.exists():
                    worksheet['A' + str(row_offset + 1)] = category
                    cell = worksheet['A' + str(row_offset + 1)]
                    cell.font = Font(color='FFFFFF')
                    cell.fill = PatternFill(fgColor='0066CC', fill_type='solid')
                    worksheet.merge_cells('A' + str(row_offset + 1) + ':D' + str(row_offset + 1))
                    row_offset += 2

                for product in products.filter(branch__name=branch):
                    if category == product.product.category.name:
                        worksheet.append([product.product.name, product.cost, product.price, product.quantity])
                        row_offset += 1

        workbook.save(response)
        return response
    
    all_branches_inventory = Inventory.objects.filter(branch=request.user.branch)
    
    totals = calculate_inventory_totals(all_branches_inventory.filter(status=True))
  
    return render(request, 'inventory/inventory.html', {
        'inventory': inventory,
        'search_query': q,
        'category':category,
        'total_price': totals[1],
        'total_cost':totals[0],
        # 'transfers_count': pending_transfers
    })
 
@login_required   
def inventory_index_json(request):
    inventory = Inventory.objects.filter(branch=request.user.branch, status=True).values(
        'id', 'product__name', 'product__id', 'price', 'cost', 'quantity', 'reorder'
    ).order_by('product__name')
    return JsonResponse(list(inventory), safe=False)

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
            inv_product.min_stock_level = request.POST['min_stock_level']
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
        return render(request, 'inventory/inventory_form.html', {'product':inv_product, 'title':f'Edit >>> {inv_product.product.name}'})

@login_required
def inventory_detail(request, id):
    q = request.GET.get('q', '')

    inventory = Inventory.objects.get(id=id, branch=request.user.branch)
    
    logs = ActivityLog.objects.filter(inventory=inventory, branch=request.user.branch)    

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
    form = addTransferForm()
    q = request.GET.get('q', '') 
    branch_id = request.GET.get('branch', '')

    transfers = Transfer.objects.filter(branch=request.user.branch).order_by('-date')
    transfer_items = TransferItems.objects.all()
    
    if q:
        transfers = transfers.filter(Q(transfer_ref__icontains=q) | Q(date__icontains=q) )
        
    if branch_id: 
        transfers =transfers.filter(to_branch__id=branch_id)
        
    if request.method == 'POST':
        form = addTransferForm(request.POST)
        
        if form.is_valid():
            transfer=form.save(commit=False)
            transfer_to = Branch.objects.get(id=int(request.POST['transfer_to']))
            transfer.branch = request.user.branch
            transfer.transfer_ref = Transfer.generate_transfer_ref(transfer.branch.name, transfer_to.name)
            
            transfer.save()
            
            return redirect('inventory:add_transfer', transfer.transfer_ref)
            
        messages.success(request, 'Transfer creation failed')
    
    return render(request, 'inventory/transfers.html', {'transfers': transfers,'search_query': q, 'form':form, 'transfer_items':transfer_items })
    
    
@login_required
def receive_inventory(request):
    q = request.GET.get('q', '')
    
    transfers =  TransferItems.objects.filter(to_branch=request.user.branch, received=False, declined=False, over_less=False)
    if q:
        transfers = transfers.filter(Q(product__name__icontains=q) |Q(date__icontains=q)) 
    
    if request.method == 'POST':
        transfer_id = request.POST.get('id')  

        try:
            branch_transfer = get_object_or_404(transfers, id=transfer_id)

            if request.POST['received'] == 'true':
                if int(request.POST['quantity']) != int(branch_transfer.quantity):
                    branch_transfer.over_less_quantity =  branch_transfer.quantity - int(request.POST['quantity']) 
                    branch_transfer.over_less = True
                    branch_transfer.save()
                    
                if Inventory.objects.filter(product=branch_transfer.product, branch=request.user.branch).exists():
                    existing_inventory = Inventory.objects.get(product=branch_transfer.product, branch=request.user.branch)
                    existing_inventory.quantity += int(request.POST['quantity'])
                    existing_inventory.price = branch_transfer.price
                    existing_inventory.save()
                    
                    branch_transfer.received = True
                    ActivityLog.objects.create(
                        branch = request.user.branch,
                        user=request.user,
                        action= 'stock in',
                        inventory=existing_inventory,
                        quantity=int(request.POST['quantity']),
                        total_quantity= existing_inventory.quantity,
                        product_transfer=branch_transfer,
                    )
                    messages.success(request, 'Product received')
                    
                else:
                    inventory = Inventory.objects.create(
                        branch=request.user.branch,
                        product=branch_transfer.product,
                        cost=branch_transfer.product.cost,  
                        price=branch_transfer.price,
                        quantity=request.POST['quantity']
                    )
                    ActivityLog.objects.create(
                        branch = request.user.branch,
                        user=request.user,
                        action= 'stock in',
                        inventory=inventory,
                        quantity=inventory.quantity,
                        total_quantity=inventory.quantity,
                        product_transfer=branch_transfer
                    )
                    messages.success(request, 'Product received')
            branch_transfer.save()
            return redirect('inventory:receive_inventory')  

        except Transfer.DoesNotExist:
            messages.error(request, 'Invalid transfer ID')
            return redirect('inventory:receive_inventory')  

    return render(request, 'inventory/receive_inventory.html', {'transfers': transfers})

@login_required
@transaction.atomic
def over_less_list_stock(request):
    form = DefectiveForm()
    search_query = request.GET.get('search_query', '')
    
    transfers =  TransferItems.objects.filter(from_branch=request.user.branch, received=True, over_less=True)
    
    if search_query:
        transfers = transfers.filter(
            Q(transfer__product__name__icontains=search_query)|
            Q(transfer__transfer_ref__icontains=search_query)|
            Q(date__icontains=search_query)
        )
        
    def activity_log(action, inventory, branch_transfer):
        ActivityLog.objects.create(
            branch = request.user.branch,
            user=request.user,
            action= action,
            inventory=inventory,
            quantity=branch_transfer.over_less_quantity,
            total_quantity=inventory.quantity,
            product_transfer=branch_transfer
        )
    
    if request.method == 'POST':
        data = json.loads(request.body)
        
        action = data['action']
        transfer_id = data['transfer_id']
        reason = data['reason']
        status = data['status']
        
        branch_transfer = get_object_or_404(transfers, id=transfer_id)
        product = Inventory.objects.get(product=branch_transfer.product, branch=request.user.branch)
       
        if int(branch_transfer.over_less_quantity) > 0:
            if action == 'write_off':    
                product.quantity += branch_transfer.over_less_quantity 
                product.save()
                
                activity_log('Stock in', product, branch_transfer )
                
                DefectiveProduct.objects.create(
                    product = product,
                    branch = request.user.branch,
                    quantity = branch_transfer.over_less_quantity,
                    reason = reason,
                    status = status
                )
                
                product.quantity -= branch_transfer.over_less_quantity 
                branch_transfer.over_less = False
                branch_transfer.save()
                product.save()
                
                activity_log('write off', product, branch_transfer )
                
                messages.success(request, f'{product.product.name} write-off successfull')        

                return JsonResponse({'success':True}, status=200)
            
            if action == 'accept':
                product.quantity += branch_transfer.over_less_quantity 
                product.save()
                
                activity_log('stock in', product, branch_transfer )
                
                branch_transfer.over_less = False
                branch_transfer.save()
                
                messages.success(request, f'{product.product.name} accepted back successfully') 

                return JsonResponse({'success':True}, status=200)
            
            if action == 'back':
                product.quantity += branch_transfer.over_less_quantity 
                product.save()
                
                activity_log('stock in', product, branch_transfer )
                
                branch_transfer.received = False
                branch_transfer.quantity = branch_transfer.over_less_quantity
                branch_transfer.save()
                
                product.quantity -= branch_transfer.over_less_quantity 
                product.save()
            
                activity_log('transfer', product, branch_transfer )
                
                branch_transfer.over_less = False
                branch_transfer.save()
                
                messages.success(request, f'{product.product.name} transfered back to {branch_transfer.to_branch.name} sucessfully') 
                
                return JsonResponse({'success':True}, status=200)
            
        messages.error(request, f'Product quantity cant be zero.')
        return redirect('inventory:over_less_list_stock')
                  
    return render(request, 'inventory/over_less_transfers.html', {'over_less_transfers':transfers, 'form':form})

@login_required
@transaction.atomic
def defective_product_list(request):
    form = RestockForm()
    defective_products = DefectiveProduct.objects.filter(branch=request.user.branch)
    
    # loss calculation
    if request.method == 'POST':
        data = json.loads(request.body)
        
        product_id = data['product_id']
        quantity = int(data['quantity'])
        
        product = Inventory.objects.get(product__id=product_id, branch=request.user.branch)
        product.quantity += quantity
        product.status = True if product.status == False else product.status
        product.save()
        
        defective_product = DefectiveProduct.objects.get(product=product, branch=request.user.branch)
        defective_product.quantity -= quantity
        defective_product.save()
        
        ActivityLog.objects.create(
            branch = request.user.branch,
            user=request.user,
            action= 'stock in',
            inventory=product,
            quantity=quantity,
            total_quantity=product.quantity,
            description = 'from defective products'
        )
        return JsonResponse({'success':True}, status=200)
    quantity = defective_products.aggregate(Sum('quantity'))['quantity__sum'] or 0
    price = defective_products.aggregate(Sum('product__cost'))['product__cost__sum'] or 0
    
    return render(request, 'inventory/defective_products.html', 
        {
            'total_cost': quantity * price,
            'defective_products':defective_products,
            'form':form
        }
    )

@login_required
def add_inventory_transfer(request, transfer_ref):
    try:
        transfer=Transfer.objects.get(transfer_ref=transfer_ref)
    except Transfer.DoesNotExist:
        transfer.delete()
        messages.error(request, f'Transfer Does not Exist')
        return redirect('inventory:transfers')
    return render(request, 'inventory/add_transfer.html', {'transfer':transfer})

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

@login_required
def reoder_list(request):
    reorder_list = ReoderList.objects.filter()
    
    if request.method == 'GET':
        if 'download' in request.GET:
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename={request.user.branch.name} stock.xlsx'
            workbook = openpyxl.Workbook()
            worksheet = workbook.active

            row_offset = 0
            
            worksheet['A' + str(row_offset + 1)] = f'Re-order Products'
            worksheet.merge_cells('A' + str(row_offset + 1) + ':D' + str(row_offset + 1))
            cell = worksheet['A' + str(row_offset + 1)]
            cell.alignment = Alignment(horizontal='center')
            cell.font = Font(size=14, bold=True)
            cell.fill = PatternFill(fgColor='AAAAAA', fill_type='solid')

            row_offset += 1 
                
            category_headers = ['Name', 'Quantity']
            for col_num, header_title in enumerate(category_headers, start=1):
                cell = worksheet.cell(row=3, column=col_num)
                cell.value = header_title
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal='center')

            categories = reorder_list.all().values_list('product__product__category__name', flat=True).distinct()
            for category in categories:
                products_in_category = reorder_list.filter(product__product__category__name=category)
                if products_in_category.exists():
                    worksheet['A' + str(row_offset + 1)] = category
                    cell = worksheet['A' + str(row_offset + 1)]
                    cell.font = Font(color='FFFFFF')
                    cell.fill = PatternFill(fgColor='0066CC', fill_type='solid')
                    worksheet.merge_cells('A' + str(row_offset + 1) + ':D' + str(row_offset + 1))
                    row_offset += 2

                for product in reorder_list:
                    if category == product.product.product.category.name:
                        worksheet.append([product.product.product.name])
                        row_offset += 1

            workbook.save(response)
            return response
        return render(request, 'inventory/reorder_list.html', {'reorder_list':reorder_list})

    if request.method == 'POST':
        data = json.loads(request.body)
        action = data['action']
        product_id = data['product_id']
    
        product = ReoderList.objects.get(id=product_id)
        inventory = Inventory.objects.get(product__id=product.product.product.id)
        
        if action == 'remove':
            product.delete()
            
            inventory.reorder=False
            inventory.save()
            
            return JsonResponse({'success':True}, status=200)
        
        elif action == 'clear':
            reorder_list.delete()
            
            inventory.reorder=False
            inventory.save()
            
            return JsonResponse({'success':True}, status=200)


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
    transfer_id = request.GET.get('transfer_id', '')
    
    
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
        
    if view or transfer_id:
        return JsonResponse(list(TransferItems.objects.filter(transfer__id=transfer_id, transfer__branch=request.user.branch).values(
                'product__name', 
                'price',
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
    