import json
import environ
import asyncio, settings
from pathlib import Path
from bleak import BleakScanner
from django.shortcuts import render
from django.http import JsonResponse
from .forms import EmailSettingsForm
from techcity.settings import INVENTORY_EMAIL_NOTIFICATIONS_STATUS
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

import logging
logger = logging.getLogger(__name__)

@login_required
def settings(request):
    email_form = EmailSettingsForm()
    env_file_path = Path(__file__).resolve().parent.parent / '.env'
    try:
        with env_file_path.open('r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    printer_data = None  

    for line in lines:
        key, *value = line.strip().split('=')
        if key == 'PRINTER_ADDRESS':
            printer_data = value[0]  

    return render(request, 'settings/settings.html', {
        'printer':printer_data, 
        'email_form':email_form,
        'email_status':INVENTORY_EMAIL_NOTIFICATIONS_STATUS
    })
    
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET", "POST"])
@login_required
def email_notification_status(request):
    if request.method == 'GET':
        return JsonResponse({'status': settings.INVENTORY_EMAIL_NOTIFICATIONS_STATUS})

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            status = data.get('status')
            if status is None:
                return JsonResponse({'success': False, 'error': 'Status not provided'}, status=400)
            settings.INVENTORY_EMAIL_NOTIFICATIONS_STATUS = status
            logger.info(f'{settings.INVENTORY_EMAIL_NOTIFICATIONS_STATUS}')
            return JsonResponse({'success': True}, status=200)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    return JsonResponse({'success': False}, status=400)

    


@csrf_exempt
@login_required
def save_email_config(request):
    if request.method == 'POST':
        env_file_path = Path(__file__).resolve().parent.parent / '.env'
   
        email_settings_mapping = {
            'EMAIL_HOST': 'EMAIL_HOST',
            'EMAIL_PORT': 'EMAIL_PORT',
            'EMAIL_USE_TLS': 'EMAIL_USE_TLS',
            'EMAIL_HOST_USER': 'EMAIL_HOST_USER',
            'EMAIL_HOST_PASSWORD': 'EMAIL_HOST_PASSWORD',
        }

        email_settings_updated = False
        new_lines = []
        keys_updated = set()

        if env_file_path.exists():
            with env_file_path.open('r') as f:
                lines = f.readlines()

            for line in lines:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    if key in email_settings_mapping:
                        new_value = request.POST.get(key)
                        if new_value is not None:
                            if key in ('EMAIL_USE_TLS', 'EMAIL_USE_SSL'):
                                new_value = str(new_value.lower() == 'true')
                            new_lines.append(f"{email_settings_mapping[key]}={new_value}\n")
                            email_settings_updated = True
                            keys_updated.add(key)
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            for key in email_settings_mapping:
                if key not in keys_updated:
                    new_value = request.POST.get(key)
                    if new_value is not None:
                        if key in ('EMAIL_USE_TLS', 'EMAIL_USE_SSL'):
                            new_value = str(new_value.lower() == 'true')
                        new_lines.append(f"{email_settings_mapping[key]}={new_value}\n")
                        email_settings_updated = True
        else:
            for key in email_settings_mapping:
                new_value = request.POST.get(key)
                if new_value is not None:
                    if key in ('EMAIL_USE_TLS', 'EMAIL_USE_SSL'):
                        new_value = str(new_value.lower() == 'true')
                    new_lines.append(f"{email_settings_mapping[key]}={new_value}\n")
                    email_settings_updated = True

        with env_file_path.open('w') as f:
            f.writelines(new_lines)

        environ.Env.read_env()

        if email_settings_updated:
            return JsonResponse({'success': True, 'message': 'Email settings updated successfully!'})
        else:
            return JsonResponse({'success': False, 'message': 'No email settings found in the form.'})

    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=400)


@csrf_exempt  
def scan_for_printers(request):
    if request.method == 'GET':
        try:
            devices = asyncio.run(BleakScanner.discover())
            printer_data = [
                {
                    'address': device.address,
                    'name': device.name or "Unknown Device",
                } 
                for device in devices 
            ]
            return JsonResponse({'printers': printer_data})
        except Exception as e:
            return JsonResponse({'error': f'Error scanning for printers: {str(e)}'}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=400)


@csrf_exempt
@login_required
def update_or_create_printer(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        printer_address = data.get('printer_address')

        if not printer_address:
            return JsonResponse({'success': False, 'error': 'Invalid printer address'})

        device = asyncio.run(get_bluetooth_device(printer_address))
        
        if device:
            env_file_path = Path(__file__).resolve().parent.parent / '.env'

            try:
                with env_file_path.open('r') as f:
                    lines = f.readlines()
            except FileNotFoundError:
                lines = []

            printer_found = False
            with env_file_path.open('w') as f:
                for line in lines:
                    key, *value = line.strip().split('=')
                    if key == 'PRINTER_ADDRESS':
                        printer_found = True
                        f.write(f"{key}={printer_address}\n")
                    else:
                        f.write(line)

                if not printer_found:
                    f.write(f"PRINTER_ADDRESS={printer_address}\n")

            environ.Env.read_env()

            return JsonResponse({'success': True, 'message': 'Printer settings updated/created successfully!'})
        else:
            return JsonResponse({'success': False, 'error': 'Selected printer not found'})
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)


async def get_bluetooth_device(address):
    devices = await BleakScanner.discover()
    device = next((d.address for d in devices ), None)
    return device


# @login_required
# def print_receipt(request, invoice_id):
#     # ... Retrieve invoice data ...
#     printer_settings = PrinterSettings.objects.first()  # Or get from session

#     if not printer_settings:
#         return JsonResponse({'success': False, 'error': 'No printer configured.'})

#     try:
#         async with BleakClient(printer_settings.address) as client:
#             print_service = await client.get_service(printer_settings.service_uuid)
#             tx_characteristic = print_service.get_characteristic(UUID_TX_CHAR)  # Get characteristic for sending data

#             # ... Format receipt data ...
#             receipt_data = format_receipt(invoice)  # Your formatting logic

#             await client.write_gatt_char(tx_characteristic, receipt_data)
            
#         return JsonResponse({'success': True})
#     except Exception as e:
#         return JsonResponse({'success': False, 'error': str(e)})