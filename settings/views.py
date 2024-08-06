import json
import environ
import asyncio, settings
from pathlib import Path
from bleak import BleakScanner
from django.shortcuts import render, redirect
from django.http import JsonResponse

from utils.identify_pc import get_mac_address, get_system_uuid, get_hostname
from .forms import EmailSettingsForm
from techcity.settings import INVENTORY_EMAIL_NOTIFICATIONS_STATUS
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

import logging

from .models import NotificationsSettings, Printer

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

    notifications_settings = NotificationsSettings.objects.filter(user=request.user).first()

    return render(request, 'settings/settings.html', {
        'printer': printer_data,
        'email_form': email_form,
        'notifications': notifications_settings
    })


from django.http import JsonResponse
from django.views.decorators.http import require_http_methods


# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>> Notifications settings >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

def validate_payload(payload):
    # check payload for status and notification
    if 'notification' not in payload:
        return JsonResponse({'success': False, 'error': 'Notification not provided'}, status=400)
    notification = payload.get('notification')
    # check if notification is in database
    logger.info(f'Notifications in database: {NotificationsSettings._meta.get_fields()}')
    if notification not in NotificationsSettings._meta.get_fields():
        return JsonResponse({'success': False, 'error': 'Invalid notification'}, status=400)

    if 'status' not in payload:
        return JsonResponse({'success': False, 'error': 'Status not provided'}, status=400)
    # if payload is empty
    if not payload:
        return JsonResponse({'success': False, 'error': 'Empty payload'}, status=400)

    status = payload.get('status')
    # check if status is valid
    if status not in ['on', 'off']:
        return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)

    return [notification, status]


# products notifications settings views
@require_http_methods(["POST"])
@login_required
def email_notification_status(request):
    """
        payload: {"notification": "product_creation","status": "on"}
    """
    if request.method == 'POST':
        try:
            payload = json.loads(request.body)
            logger.info(f'Payload: {payload}')
            # result = validate_payload(payload)  # validate payload
            # logger.info(f'Payload validated: {result}')
            notification = payload.get('notification')
            status = payload.get('status')
            logger.info(f'Payload validated: {notification}, {status}')
            # update status from NotificationsSettings model
            notification_instance = NotificationsSettings.objects.first()
            logger.info(f'Notification instance: {notification_instance}')
            if notification_instance:
                # update notification_instance
                if status:
                    setattr(notification_instance, notification, True)
                elif not status:
                    setattr(notification_instance, notification, False)
                notification_instance.save()
            logger.info(f'Notification: {notification} Status: {status}, updated successfully')
            return JsonResponse({'success': True}, status=200)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


# @require_http_methods(["POST"])
# @login_required
# def email_notification_status(request):
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body)
#             status = data.get('status')
#             if status is None:
#                 return JsonResponse({'success': False, 'error': 'Status not provided'}, status=400)
#             settings.INVENTORY_EMAIL_NOTIFICATIONS_STATUS = status
#             logger.info(f'{settings.INVENTORY_EMAIL_NOTIFICATIONS_STATUS}')
#             return JsonResponse({'success': True}, status=200)
#         except json.JSONDecodeError:
#             return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


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


# >>>>>>>>>>>>>>>>>>>>>>>>>>> PRINTER SETTINGS >>>>>>>>>>>>>>>>>>>>>>>>>>

@require_http_methods(["POST"])
def add_printer(request):
    """
    Add printer details to DB:

    payload = {
        printer_name: printerName,
        printer_address: printerAddress,
        pc_identifier: pcIdentifier,
        hostname: hostname
    }

    """
    if request.method == 'POST':
        payload = json.loads(request.body)
        logger.info(f"payload: {payload}")

        name = payload.get('printer_name')
        address = payload.get('printer_address')
        hostname = payload.get('hostname')
        pc_identifier = payload.get('pc_identifier')

        if name and address and hostname and pc_identifier:
            logger.info(f"saving printer details")
            printer = Printer.objects.create(
                name=name,
                address=address,
                hostname=hostname,
                pc_identifier=pc_identifier,
                printer_type='system',

            )
            logger.info(f"printer {printer.name} added successfully: {printer}")
            return JsonResponse({"success": True, "message": "Printer added successfully"}, status=200)


def scan_printers(request):
    """
    Scan locally configured Printer settings in this OS, filter out printers already in the system
    """
    logger.info(f"scanning printers")
    printers = [
        {'name': 'Printer 1', 'address': '192.168.1.100'},
        {'name': 'Printer 2', 'address': '192.168.1.101'},
    ]
    logger.info(f"scanning successful")
    return JsonResponse({"success": True, "printers": printers}, safe=False, status=200)


def identify_pc(request):
    """
    Identify the PC using MAC address AND system uuid
    """
    mac_address = get_mac_address()
    system_uuid = get_system_uuid()
    hostname = get_hostname()
    return JsonResponse({"status": True, "mac_address": mac_address, "system_uuid": system_uuid, "hostname": hostname}, status=200)


# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>> DONE >>>>>>>>>>>>>>>>>>>>>>>>...

async def get_bluetooth_device(address):
    devices = await BleakScanner.discover()
    device = next((d.address for d in devices), None)
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
