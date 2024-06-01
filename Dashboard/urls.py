from django.urls import path
from . views import *

app_name='dashboard'

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('get_partial_invoice_details/<int:invoice_id>/', get_partial_invoice_details, name='get_partial_invoice_details')
]
