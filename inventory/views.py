import json, datetime, openpyxl 
from datetime import timedelta
from openpyxl.styles import Alignment, Font, PatternFill
from . models import *
from . tasks import send_transfer_email
from decimal import Decimal
from django.views import View
from django.db.models import Q
from django.db.models import Sum
from django.db import transaction
from django.contrib import messages
from utils.utils import generate_pdf
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponse
from finance.models import StockTransaction
from . utils import calculate_inventory_totals
from . forms import (
    AddProductForm, 
    addCategoryForm, 
    addTransferForm, 
    DefectiveForm,
    RestockForm, 
    AddDefectiveForm, 
    ServiceForm, 
    AddSupplierForm,
    CreateOrderForm
)
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from channels.generic.websocket import  AsyncJsonWebsocketConsumer
from django.shortcuts import render, redirect, get_object_or_404, get_list_or_404
from permissions.permissions import (
    admin_required,
    # sales_required, 
    # accountant_required
)


import logging
logger = logging.getLogger(__name__)

@login_required
def notifications_json(request):
    notifications = StockNotifications.objects.filter(inventory__branch=request.user.branch).values(
        'inventory__product__name', 'type', 'notification', 'inventory__id'
    )
    return JsonResponse(list(notifications), safe=False)

@login_required
def service(request):
    form = ServiceForm()
    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Service successfully created')
            return redirect('inventory:inventory')
        messages.warning(request, 'Invalid form data')
    return redirect('inventory:inventory')
    

@login_required
def product_list(request): 
    """ for the pos """
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
        'id', 
        'product__id', 
        'product__name', 
        'product__description', 
        'product__category__id', 
        'product__category__name',  
        'product__end_of_day',
        'price', 
        'quantity'
    ))
    
    merged_data = [{
        'inventory_id': item['id'],
        'product_id': item['product__id'],
        'product_name':item['product__name'],
        'description': item['product__description'],
        'category': item['product__category__id'],
        'category_name': item['product__category__name'],
        'end_of_day':item['product__end_of_day'],
        'price': item['price'],
        'quantity': item['quantity'],
    } for item in inventory_data]

    return JsonResponse(merged_data, safe=False)

@login_required
def branches_inventory(request):
    return render(request, 'inventory/branches_inventory.html')

@login_required
def branches_inventory_json(request):
    branches_inventory = Inventory.objects.filter(status=True).values(
        'product__name', 'price', 'quantity', 'branch__name'
    )
    return JsonResponse(list(branches_inventory), safe=False)
        
class AddProductView(LoginRequiredMixin, View):
    form_class = AddProductForm()
    initial = {'key':'value'}
    template_name = 'inventory/add_product.html'
    
    def get(self, request, *args, **kwargs):
        form = self.form_class
        return render(request, self.template_name, {'form': form})
    
    def post(self, request, *args, **kwargs):
        if request.method == 'POST':
            form = AddProductForm(request.POST)
            product_name = request.POST['name']
            
            try:
                product = Product.objects.get(name=product_name)                
                messages.warning(request, 'Product exists ')
                return redirect('inventory:add_product')
            except Product.DoesNotExist:
                if form.is_valid():
                    product = form.save()
                    message = 'Product successfully created'
                    log_action = 'stock in'
                else:
                    messages.warning(request, 'Invalid form data')
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

class ProcessTransferCartView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                logger.info('processing')
                data = json.loads(request.body)
                branch_name = data['branch_to']
                
                try:
                    branch_to =  Branch.objects.get(name=branch_name)
                except Exception as e:
                    return JsonResponse({'success':False, 'message': f'here {e}'})
                
                transfer = Transfer(
                    transfer_to = branch_to,
                    branch = request.user.branch,
                    user = request.user,
                    transfer_ref = Transfer.generate_transfer_ref(request.user.branch.name, branch_to.name)
                )
                
                logger.info(f'transfer: {data['cart']}')
                for item in data['cart']:
                    logger.info(type(item))
                    transfer_item = TransferItems(
                        transfer=transfer,
                        product= Product.objects.get(name=item['product']),
                        price=item['price'],
                        quantity=item['quantity'],
                        from_branch= request.user.branch,
                        to_branch= transfer.transfer_to,
                    )   
                    transfer.save()         
                    transfer_item.save()
                    logger.info(f'transfer {transfer}')
                    logger.info(f'transfer item: {transfer_item}')
                    
                    self.deduct_inventory(transfer_item)
                    self.transfer_update_quantity(transfer_item, transfer)  
                    
                # send email for transfer alert
                # transaction.on_commit(lambda: send_transfer_email(request.user.email, transfer.id, transfer.transfer_to.id))
                
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    def deduct_inventory(self, transfer_item):
        logger.info(f'from branch -> {transfer_item.from_branch}')
        branch_inventory = Inventory.objects.get(product__name=transfer_item.product, branch__name=transfer_item.from_branch)
        
        branch_inventory.quantity -= int(transfer_item.quantity)
        branch_inventory.save()
        self.activity_log('Transfer', branch_inventory, transfer_item)
        
    def transfer_update_quantity(self, transfer_item, transfer):
        transfer = Transfer.objects.get(id=transfer.id)
        transfer.quantity += transfer_item.quantity
        transfer.save()
       
    def activity_log(self,  action, inventory, transfer_item,):
        ActivityLog.objects.create(
            invoice = None,
            product_transfer = transfer_item,
            branch = self.request.user.branch,
            user=self.request.user,
            action= action,
            inventory=inventory,
            quantity=transfer_item.quantity,
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
    return JsonResponse(list(transfer), safe=False)

@login_required
def inventory(request):
    product_name = request.GET.get('name', '')
    if product_name:
        logger.info(f'{list(Inventory.objects.filter(product__name=product_name, branch=request.user.branch).values())}')
        return JsonResponse(list(Inventory.objects.filter(product__name=product_name, branch=request.user.branch).values()), safe=False)
    return JsonResponse({'error':'product doesnt exists'})


@login_required
def inventory_index(request):
    form = ServiceForm()
    q = request.GET.get('q', '')  
    category = request.GET.get('category', '')    
    
    services = Service.objects.all().order_by('-name')
    inventory = Inventory.objects.filter(branch=request.user.branch, status=True).order_by('product__name')
    
    if category:
        if category == 'inactive':
            inventory = Inventory.objects.filter(branch=request.user.branch, status=False)
        else:
            inventory = inventory.filter(product__category__name=category)
                
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
        'form': form,
        'services':services,
        'inventory': inventory,
        'search_query': q,
        'category':category,
        'total_price': totals[1],
        'total_cost':totals[0],
    })

@login_required
def edit_service(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    if request.method == 'GET':
        form = ServiceForm(instance=service)
        return render(request, 'inventory/edit_service.html', {'form': form, 'service': service})
    
    elif request.method == 'POST':
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, f'{service.name} successfully edited')
            return redirect('inventory:inventory')
        else:
            messages.warning(request, 'Please correct the errors below')
    
    else:
        messages.warning(request, 'Invalid request')
        return redirect('inventory:inventory')
    
    return render(request, 'inventory/edit_service.html', {'form': form, 'service': service})
        
@login_required   
def inventory_index_json(request):
    inventory = Inventory.objects.filter(branch=request.user.branch, status=True).values(
        'id', 'product__name', 'product__quantity', 'product__id', 'price', 'cost', 'quantity', 'reorder'
    ).order_by('product__name')
    return JsonResponse(list(inventory), safe=False)

@login_required 
@transaction.atomic
def activate_inventory(request, product_id):
    product = get_object_or_404(Inventory, id=product_id)
    product.status=True
    product.save()
    
    ActivityLog.objects.create(
        invoice = None,
        product_transfer = None,
        branch = request.user.branch,
        user=request.user,
        action= 'activated',
        inventory=product,
        quantity=product.quantity,
        total_quantity=product.quantity
    )
    
    messages.success(request, 'Product succefully activated')
    return redirect('inventory:inventory')

@admin_required
@login_required
def edit_inventory(request, product_name):
    inv_product = Inventory.objects.get(product__name=product_name, branch=request.user.branch)

    if request.method == 'POST':
        
        product = Product.objects.get(name=product_name)
        product.name=request.POST['name']
        product.batch_code=request.POST['batch_code']
        product.description=request.POST['description']
        
        end_of_day = request.POST.get('end_of_day')

        if end_of_day:
            product.end_of_day = True
            
        product.save()
        
        quantity = int(request.POST['quantity'])
        
        inv_product.quantity += quantity
            
        inv_product.price = Decimal(request.POST['price'])
        inv_product.cost = Decimal(request.POST['cost'])
        inv_product.min_stock_level = request.POST['min_stock_level']
        logger.info(f'msl -> {inv_product.min_stock_level}')
        inv_product.save()
        
        ActivityLog.objects.create(
            branch = request.user.branch,
            user=request.user,
            action= 'Stock in' if quantity > 0 else 'removed',
            inventory=inv_product,
            quantity=quantity,
            total_quantity=inv_product.quantity,
        )
        
        messages.success(request, f'{product.name} update succesfully')
        return redirect('inventory:inventory')
    return render(request, 'inventory/inventory_form.html', {'product':inv_product, 'title':f'Edit >>> {inv_product.product.name}'})

@login_required
def inventory_detail(request, id):

    inventory = Inventory.objects.get(id=id, branch=request.user.branch)
    logs = ActivityLog.objects.filter(inventory=inventory, branch=request.user.branch)

    sales_data = {}
    stock_in_data = {}
    transfer_data = {}
    labels = []

    for log in logs:
        month_name = log.timestamp.strftime('%B')  
        year = log.timestamp.strftime('%Y')
        month_year = f"{month_name} {year}"  

        if log.action == 'Sale':
            if month_year in sales_data:
                sales_data[month_year] += log.quantity
            else:
                sales_data[month_year] = log.quantity
        elif log.action in ('stock in', 'Update'):
            if month_year in stock_in_data:
                stock_in_data[month_year] += log.quantity
            else:
                stock_in_data[month_year] = log.quantity
        elif log.action == 'Transfer':
            if month_year in transfer_data:
                transfer_data[month_year] += log.quantity
            else:
                transfer_data[month_year] = log.quantity

        if month_year not in labels:
            labels.append(month_year)

    return render(request, 'inventory/inventory_detail.html', {
        'inventory': inventory,
        'logs': logs,
        'sales_data': list(sales_data.values()), 
        'stock_in_data': list(stock_in_data.values()),
        'transfer_data': list(transfer_data.values()),
        'labels': labels
    })


@login_required    
def inventory_transfers(request):
    form = addTransferForm()
    q = request.GET.get('q', '') 
    branch_id = request.GET.get('branch', '')

    transfers = Transfer.objects.filter(branch=request.user.branch).order_by('-time')
    transfer_items = TransferItems.objects.all()
    
    if q:
        transfers = transfers.filter(Q(transfer_ref__icontains=q) | Q(date__icontains=q) )
        
    if branch_id: 
        transfers = transfers.filter(transfer_to__id=branch_id)
        
    if request.method == 'POST':
        form = addTransferForm(request.POST)
        
        if form.is_valid():
            transfer=form.save(commit=False)
            transfer_to = Branch.objects.get(id=int(request.POST['transfer_to']))
            transfer.branch = request.user.branch
            transfer.user = request.user
            transfer.transfer_ref = Transfer.generate_transfer_ref(transfer.branch.name, transfer_to.name)
            
            transfer.save()
            
            return redirect('inventory:add_transfer', transfer.transfer_ref)
            
        messages.success(request, 'Transfer creation failed')
    
    return render(request, 'inventory/transfers.html', {'transfers': transfers,'search_query': q, 'form':form, 'transfer_items':transfer_items })

@login_required
def print_transfer(request, transfer_id):
    
    try:
        transfer = Transfer.objects.get(id=transfer_id)
    except:
        messages.warning(request, 'Transfer doesnt exists')
        return redirect('inventory:transfers')
    
    transfer_items = TransferItems.objects.filter(transfer=transfer)
    
    return render(request, 'inventory/components/ibt.html', {
        'date':datetime.datetime.now(),
        'transfer':transfer, 
        'transfer_items':transfer_items
    })
    
@login_required
@transaction.atomic
def receive_inventory(request):
    transfers =  TransferItems.objects.filter(to_branch=request.user.branch).order_by('-date')
    all_transfers = Transfer.objects.filter(transfer_to=request.user.branch).order_by('-time')    

    if request.method == 'POST':
        transfer_id = request.POST.get('id')  

        try:
            branch_transfer = get_object_or_404(transfers, id=transfer_id)
            transfer_obj = get_object_or_404(all_transfers, id=branch_transfer.transfer.id)
            # validation
            if int(request.POST['quantity']) > branch_transfer.quantity:
                messages.error(request, 'Quantity received cannot be more than quanity transfered') 
                return redirect('inventory:receive_inventory')
                
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
                    
                    ActivityLog.objects.create(
                        branch = request.user.branch,
                        user=request.user,
                        action= 'stock in',
                        inventory=existing_inventory,
                        quantity=int(request.POST['quantity']),
                        total_quantity= existing_inventory.quantity,
                        product_transfer=branch_transfer,
                        description = f'received f{request.POST['quantity']} out of {branch_transfer.quantity}' 
                    )
                    messages.success(request, 'Product received')
                    
                else:
                    inventory = Inventory.objects.create(
                        branch=request.user.branch,
                        product=branch_transfer.product,
                        cost=branch_transfer.product.cost,  
                        price=branch_transfer.price,
                        quantity=request.POST['quantity'],
                    )
                    ActivityLog.objects.create(
                        branch = request.user.branch,
                        user=request.user,
                        action= 'stock in',
                        inventory=inventory,
                        quantity=inventory.quantity,
                        total_quantity=inventory.quantity,
                        product_transfer=branch_transfer,
                        description = f'received {request.POST['quantity']} out of {branch_transfer.quantity}'
                    )
                    messages.success(request, 'Product received')
                    
            branch_transfer.quantity_track = branch_transfer.quantity - int(request.POST['quantity'])
            branch_transfer.received_by = request.user
            branch_transfer.received = True
            branch_transfer.description = f'received {request.POST['quantity']} - {branch_transfer.quantity}'
            branch_transfer.save()
            
            transfer_obj.total_quantity_track -= int(request.POST['quantity'])
            transfer_obj.save()
            return redirect('inventory:receive_inventory')  

        except Transfer.DoesNotExist:
            messages.error(request, 'Invalid transfer ID')
            return redirect('inventory:receive_inventory')  
    return render(request, 'inventory/receive_inventory.html', {'r_transfers': transfers, 'transfers':all_transfers})

@login_required
def receive_inventory_json(request):
    transfers =  TransferItems.objects.filter(to_branch=request.user.branch).order_by('-date')
    if request.method ==  'GET':
        transfers = transfers.values(
            'id',
            'date', 
            'quantity',
            'received', 
            'description',
            'date_received',
            'product__name', 
            'from_branch__name',
            'received_by__username'
        )
        return JsonResponse(list(transfers), safe=False)
    
@login_required
@transaction.atomic
def over_less_list_stock(request):
    form = DefectiveForm()
    search_query = request.GET.get('search_query', '')
    
    transfers =  TransferItems.objects.filter(to_branch=request.user.branch)

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
        branch_loss = data['branch_loss']
        quantity= data['quantity']
  
        branch_transfer = get_object_or_404(transfers, id=transfer_id)
        transfer = get_object_or_404(Transfer, id=branch_transfer.transfer.id)
        product = Inventory.objects.get(product=branch_transfer.product, branch=request.user.branch)
       
        if int(branch_transfer.over_less_quantity) > 0:
            if action == 'write_off':    
                product.quantity += branch_transfer.over_less_quantity 
                product.save()
                
                description='write_off'
                
                activity_log('Stock in', product, branch_transfer)
                logger.info(f'quantity {quantity}')
                DefectiveProduct.objects.create(
                    product = product,
                    branch = request.user.branch,
                    quantity = quantity,
                    reason = reason,
                    status = status,
                    branch_loss = get_object_or_404(Branch, id=branch_loss),
                )
                
                product.quantity -= branch_transfer.over_less_quantity 
                branch_transfer.over_less_description = description
                branch_transfer.action_by = request.user
                branch_transfer.over_less = False
                
                transfer.defective_status = True
                
                transfer.save()
                branch_transfer.save()
                product.save()
                
                activity_log('write off', product, branch_transfer )
                
                messages.success(request, f'{product.product.name} write-off successfull')        

                return JsonResponse({'success':True}, status=200)
            
            if action == 'accept':
                product.quantity += branch_transfer.over_less_quantity 
                product.save()
                description='returned back'
                activity_log('stock in', product, branch_transfer )
                
                branch_transfer.over_less = False
                branch_transfer.over_less_description = description
                branch_transfer.save()
                
                messages.success(request, f'{product.product.name} accepted back successfully') 

                return JsonResponse({'success':True}, status=200)
            
            if action == 'back':
                description=f'transfered to {branch_transfer.to_branch}'
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
                branch_transfer.over_less_description = description
                branch_transfer.save()
                 
                return JsonResponse({'success':True}, status=200)
            
            return JsonResponse({'success':False, 'messsage':'Invalid form'}, status=400)
            
        return JsonResponse({'success':False, 'messsage':'Invalid form'}, status=400)
                  
    return render(request, 'inventory/over_less_transfers.html', {'over_less_transfers':transfers, 'form':form})

@login_required
@transaction.atomic
def defective_product_list(request):
    form = RestockForm()
    defective_products = DefectiveProduct.objects.filter(branch=request.user.branch)
    
    # loss calculation
    if request.method == 'POST':
        data = json.loads(request.body)
        
        defective_id = data['product_id']
        quantity = data['quantity']
        
        try:
            d_product = DefectiveProduct.objects.get(id=defective_id, branch=request.user.branch)
            product = Inventory.objects.get(product__id=d_product.product.id, branch=request.user.branch)
        except:
            return JsonResponse({'success': False, 'message':'Product doesnt exists'}, status=400)
    
        product.quantity += quantity
        product.status = True if product.status == False else product.status
        product.save()
        
        d_product.quantity -= quantity
        d_product.save()
        
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
            'form':form,
        }
    )
    
@login_required
@transaction.atomic
def create_defective_product(request):
    form = AddDefectiveForm()
    if request.method == 'POST':
        form = AddDefectiveForm(request.POST)

        if form.is_valid():
            branch = request.user.branch
            product = form.cleaned_data['product']
            quantity = form.cleaned_data['quantity']
            
            # validation
            if quantity > product.quantity:
                messages.warning(request, 'Defective quantity cannot more than the products quantity')
                return redirect('inventory:create_defective_product')
            elif quantity == 0:
                messages.warning(request, 'Defective quantity cannot be less than zero')
                return redirect('inventory:create_defective_product')
            
            product.quantity -= quantity
            product.save()
        
            d_obj = form.save(commit=False)
            d_obj.branch = branch
            d_obj.branch_loss = branch
            
            d_obj.save()
            
            ActivityLog.objects.create(
                branch = branch,
                user=request.user,
                action= 'defective',
                inventory=product,
                quantity=quantity,
                total_quantity=product.quantity,
                description = ''
            )
            messages.success(request, 'Product successfuly saved')
            return redirect('inventory:defective_product_list')
        else:
            messages.success(request, 'Invalid form data')
    return render(request, 'inventory/add_defective_product.html', {'form':form})
        

@login_required
def add_inventory_transfer(request):
    form = addTransferForm()
    return render(request, 'inventory/add_transfer.html', {'fornm':form})

@login_required
@admin_required
def delete_inventory(request):
    product_id = request.GET.get('product_id', '')
    
    if product_id:
        inv = Inventory.objects.get(id=product_id, branch=request.user.branch)
        inv.status = False
        inv.save()
    
    ActivityLog.objects.create(
            branch = request.user.branch,
            user=request.user,
            action= 'deactivated',
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
def reorder_list(request):
    reorder_list = ReorderList.objects.filter(branch=request.user.branch)
        
    if request.method == 'GET':
        if 'download' in request.GET:
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename={request.user.branch.name} order.xlsx'
            workbook = openpyxl.Workbook()
            worksheet = workbook.active

            row_offset = 0
            
            worksheet['A' + str(row_offset + 1)] = f'Order List'
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

            categories = reorder_list.values_list('product__product__category__name', flat=True).distinct()
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
        return render(request, 'inventory/reorder_list.html', {})
        
@login_required
def reorder_list_json(request):
    order_list = ReorderList.objects.filter(branch=request.user.branch).values(
        'id', 
        'product__product__name',  
        'product__quantity',
        'quantity'
    )
    return JsonResponse(list(order_list), safe=False)

@login_required
@transaction.atomic
def clear_reorder_list(request):
    if request.method == 'GET':
        reorders = ReorderList.objects.filter(branch=request.user.branch)
        
        for item in reorders:
            inventory_items = Inventory.objects.filter(id=item.product.id)
            for product in inventory_items:
                product.reorder = False
                product.save()
            
        reorders.delete()
        
        messages.success(request, 'Reoder list success fully cleared')
        return redirect('inventory:reorder_list')

    if request.method == 'POST':
        data = json.loads(request.body)
        product_id = data['product_id']
    
        product = ReorderList.objects.get(id=product_id, branch=request.user.branch)
     
        inventory = Inventory.objects.get(id=product.product.id)
    
        product.delete()
        
        inventory.reorder=False
        inventory.save()
        
        return JsonResponse({'success':True}, status=200)
    
        
@login_required
@transaction.atomic
def create_order_list(request):
    if request.method == 'GET':
        products_below_five = Inventory.objects.filter(branch=request.user.branch, quantity__lte = 5).values(
            'id', 
            'product__id', 
            'product__name',
            'product__description',
            'quantity', 
            'reorder',
            'product__category__id',
            'product__category__name'
        )
        return JsonResponse(list(products_below_five), safe=False)
    
    if request.method == 'POST':
        data = json.loads(request.body)
        product_id = data['id']
        
        product = get_object_or_404(Inventory, id=product_id, branch=request.user.branch)
        ReorderList.objects.create(product=product, branch=request.user.branch)
        
        product.reorder = True
        product.save()
        return JsonResponse({'success': True}, status=201)
    return JsonResponse({'success': False, 'message':'Failed to add the product'}, status=400)
        
    

@login_required
def inventory_pdf(request):
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
    
    template_name = 'inventory/reports/transfers.html'

    view = request.GET.get('view', '')
    choice = request.GET.get('type', '') 
    time_frame = request.GET.get('timeFrame', '')
    branch_id = request.GET.get('branch', '')
    product_id = request.GET.get('product', '')
    transfer_id = request.GET.get('transfer_id', '')
    
    transfers = TransferItems.objects.filter().order_by('-date') 
    
    today = datetime.date.today()
    
    if choice in ['All', '', 'Over/Less']:
        transfers = transfers
    
    if product_id:
        transfers = transfers.filter(product__id=product_id)
    if branch_id:
        transfers = transfers.filter(to_branch_id=branch_id)
    
    def filter_by_date_range(start_date, end_date):
        return transfers.filter(date__range=[start_date, end_date])
    
    date_filters = {
        'All': lambda: transfers, 
        'today': lambda: filter_by_date_range(today, today),
        'yesterday': lambda: filter_by_date_range(today - timedelta(days=1), today - timedelta(days=1)),
        'this week': lambda: filter_by_date_range(today - timedelta(days=today.weekday()), today),
        'this month': lambda: transfers.filter(date__month=today.month, issue_date__year=today.year),
        'this year': lambda: transfers.filter(date__year=today.year),
    }
    
    
    if time_frame in date_filters:
        transfers = date_filters[time_frame]()
         
    if view:
        return JsonResponse(list(transfers.values(
                'date',
                'product__name', 
                'price',
                'quantity', 
                'from_branch__name',
                'from_branch__id',
                'to_branch__id',
                'to_branch__name',
                'received_by__username',
                'date_received',
                'description',
                'received',
                'declined'
            )), 
            safe=False
        )
    
    if transfer_id:
        
        return JsonResponse(list(transfers.filter(id=transfer_id).values(
                'date',
                'product__name', 
                'price',
                'quantity', 
                'from_branch__name',
                'from_branch__id',
                'to_branch__id',
                'to_branch__name',
                'received_by__username',
                'date_received',
                'description',
                'received',
                'declined'
            )), 
            safe=False
        )
    
    return generate_pdf(
        template_name,
        {
            'title': 'Transfers', 
            'date_range': time_frame if time_frame else 'All',
            'report_date': datetime.date.today(),
            'transfers':transfers
        },
    )


@login_required
def reorder_from_notifications(request):
    if request.method == 'GET':
        notifications = StockNotifications.objects.filter(inventory__branch=request.user.branch, inventory__reorder=False, inventory__alert_notification=False).values(
            'quantity',
            'inventory__product__name', 
            'inventory__id', 
            'inventory__quantity' 
        )
        return JsonResponse(list(notifications), safe=False)
    
    if request.method == 'POST':
        # payload
        """
            inventory_id
        """
        
        data = json.loads(request.body)
        
        inventory_id = data['inventory_id']
        action_type = data['action_type']
        
        try:
            inventory = Inventory.objects.get(id=inventory_id)
            stock_notis = StockNotifications.objects.get(inventory=inventory)
        except Exception as e:
            return JsonResponse({'success':False, 'message':f'{e}'}, status=400)
        
        if action_type == 'add':
            inventory.reorder=True
            inventory.save()
            ReorderList.objects.create(
                quantity=0,
                product=inventory, 
                branch=request.user.branch
            )
            
        elif action_type == 'remove':
            inventory.alert_notification=True
            inventory.save()
    
        return JsonResponse({'success':True}, status=200)
    
    return JsonResponse({'success':False, 'message': 'Invalid request'}, status=400)

@login_required
def add_reorder_quantity(request):
    """
    Handles adding a quantity to a reorder item.

    Payload:
    - reorder_id: ID of the reorder item
    - quantity: Quantity to add
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON payload'}, status=400)

    reorder_id = data.get('reorder_id')
    reorder_quantity = data.get('quantity')

    if not reorder_id:
        return JsonResponse({'success': False, 'message': 'Reorder ID is required'}, status=400)

    if not reorder_quantity:
        return JsonResponse({'success': False, 'message': 'Reorder quantity is required'}, status=400)

    try:
        reorder_quantity = int(reorder_quantity)
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid reorder quantity'}, status=400)

    try:
        reorder = ReorderList.objects.get(id=reorder_id)
        reorder.quantity = reorder_quantity
        reorder.save()
        logger.info(reorder.quantity)
        return JsonResponse({'success': True, 'message': 'Reorder quantity updated successfully'}, status=200)
    except ReorderList.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Reorder item not found'}, status=404)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return JsonResponse({'success': False, 'message': 'An error occurred'}, status=500)

@login_required
def suppliers(request):
    form = AddSupplierForm()
    suppliers = Supplier.objects.all()
    return render(request, 'inventory/suppliers.html', 
        {
            'suppliers':suppliers,
            'form':form
        }
    )

@login_required
def supplier_list_json(request):
    products = Product.objects.all().values(
        'id',
        'name'
    )
    return JsonResponse(list(products), safe=False)

@login_required
def create_supplier(request):
    #payload
    """
        name 
        contact
        email
        phone 
        address
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        
        name = data['name']
        contact = data['contact']
        email = data['email']
        phone = data['phone']
        address = data['address']
        
        if not name or not contact or not email or not phone or not address:
            return JsonResponse({'success': False, 'message':'Fill in all the form data'}, status=400)
        
        if Supplier.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'message':f'Supplier{name} already exists'}, status=400)
        
        supplier = Supplier(
            name = name,
            contact = contact,
            email = email,
            phone = phone,
            address = address
        )
        supplier.save()
        logger.info(f'Supplier successfully created {supplier.name}')
        return JsonResponse({'success': True}, status=200)
        
@login_required
def edit_supplier(request, supplier_id):
    # payload
    """
        supplier_id
    """
    
    if request.method == 'POST':
        data = json.loads(request.post)
        supplier_id = data['supplier_id']
        
        if supplier_id:
            try:
                supplier = Supplier.objects.get(id=supplier_id)
            except Exception as e:
                return JsonResponse({'success': False, 'message':f'{supplier_id} does not exists'}, status=400)
                
        form = AddSupplierForm(request.post, instance=supplier)
        
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True}, status=400)
    return JsonResponse({'success': True})

@login_required
def purchase_orders(request):
    form = CreateOrderForm()
    orders = PurchaseOrder.objects.filter(branch = request.user.branch)
    return render(request, 'inventory/suppliers/purchase_orders.html', 
        {
            'form':form,
            'orders':orders
        }
    )
    
@login_required
def create_purchase_order(request):
    
    if request.method == 'GET':
        supplier_form = AddSupplierForm()
        product_form = AddProductForm()
        suppliers = Supplier.objects.all()
        return render(request, 'inventory/create_purchase_order.html',
            {
                'product_form':product_form,
                'supplier_form':supplier_form,
                'suppliers':suppliers
            }
        )

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            purchase_order_data = data.get('purchase_order', {})
            purchase_order_items_data = data.get('items', [])
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON payload'}, status=400)

        supplier_id = purchase_order_data.get('supplier_id')
        delivery_date = purchase_order_data.get('delivery_date')
        status = purchase_order_data.get('status')
        notes = purchase_order_data.get('notes')

        if not all([supplier_id, delivery_date, status]):
            return JsonResponse({'success': False, 'message': 'Missing required fields'}, status=400)

        try:
            supplier = Supplier.objects.get(id=supplier_id)
        except Supplier.DoesNotExist:
            return JsonResponse({'success': False, 'message': f'Supplier with ID {supplier_id} not found'}, status=404)

        try:
            with transaction.atomic():
                purchase_order = PurchaseOrder(
                    order_number=PurchaseOrder.generate_order_number(),
                    supplier=supplier,
                    delivery_date=delivery_date,
                    status=status,
                    notes=notes
                )
                purchase_order.save()

                for item_data in purchase_order_items_data:
                    product_id = item_data.get('product')
                    quantity = item_data.get('quantity')
                    unit_cost = item_data.get('unit_cost')

                    if not all([product_id, quantity, unit_cost]):
                        transaction.set_rollback(True)
                        return JsonResponse({'success': False, 'message': 'Missing fields in item data'}, status=400)

                    try:
                        product = Product.objects.get(id=product_id)
                    except Product.DoesNotExist:
                        transaction.set_rollback(True)
                        return JsonResponse({'success': False, 'message': f'Product with ID {product_id} not found'}, status=404)

                    PurchaseOrderItem.objects.create(
                        purchase_order=purchase_order,
                        product=product,
                        quantity=quantity,
                        unit_cost=unit_cost
                    )

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

        return JsonResponse({'success': True, 'message': 'Purchase order created successfully'})

@login_required
def delete_purchase_order(request, purchase_order_id):
    if request.method != "DELETE":
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)

    try:
        purchase_order = PurchaseOrder.objects.get(id=purchase_order_id)
    except PurchaseOrder.DoesNotExist:
        return JsonResponse({'success': False, 'message': f'Purchase order with ID {purchase_order_id} not found'}, status=404)

    try:
        purchase_order.delete()
        return JsonResponse({'success': True, 'message': 'Purchase order deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
def product(request):

    if request.method == 'POST':
        # payload
        """
            name,
            prince: float,
            cost: float,
            quantity: int,
            category,
            tax_type,
            min_stock_level,
            description
        """
        try:
            data = json.loads(request.body)
        except Exception as e:
            return JsonResponse({'success':False, 'message':'Invalid data'})
        
        logger.info(f'product data -> {data}')
        
        product = Product.objecs.create(
            name = data.name,
            price = data.price,
            cost = data.cost,
            quantity = data.quantity,
            category = data.category,
            tax_type = data.tax_type,
            min_stock_level = data.min_stock_level,
            description = data.description, 
            end_of_day = data.end_of_day
        )
        product.save()
        
        # try:
        #     saved_product = Product.objects.get(id=product.id)
        # except Exception as e:
        #     return JsonResponse({'success':False, 'message':'Product Does not Exists'})
        
        return JsonResponse({'success':True})
            
    if request.method == 'GET':
        products = Product.objects.all().values(
            'id',
            'name'
        )
        return JsonResponse(list(products), safe=False)
    
    return JsonResponse({'success':False, 'message':'Invalid request'})


        
                    
        