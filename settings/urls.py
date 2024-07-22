from django.urls import path
from . views import *

app_name = 'settings'

urlpatterns = [
    path('', settings, name='settings'),
    
    # printing
    path('printer/scan/', scan_for_printers, name='scan_for_printers'),
    path('printer/create_update/', update_or_create_printer, name='update_or_create_printer'),
    
    # email
    path('email/config/save/',  save_email_config, name='save_email_config'),
    path('email/notification/status/', email_notification_status, name='email_notification_status'),
    
]