from django.urls import path
from . views import *

app_name = 'finance'

urlpatterns = [
    path('', Finance.as_view(), name='finance'),
    
    # expenses
    path('expenses/', ExpenseView.as_view(), name='expense_list'),  
    path('expenses/add/', create_expense, name='expense_create'),  
    path('expenses/<int:pk>/', ExpenseView.as_view(), name='expense_detail'),  
    path('expenses/<int:pk>/update/', ExpenseView.as_view(), name='expense_update'), 
    path('expenses/<int:pk>/delete/', ExpenseView.as_view(), name='expense_delete'),  
    path('expense/category/add', create_expense_category, name='create_expense_category' ),
    
    #invoice
    path('invoice/', invoice, name='invoice'),
    path('invoice/pdf/', invoice_pdf, name='invoice_pdf'),
    path('invoice/create/', create_invoice, name='create_invoice'),
    path('invoice/update/<str:invoice_number>/', update_invoice, name='update_invoice'),
    path('invoice/preview/<int:invoice_id>/', invoice_preview, name='invoice_preview'),
    
    #customer
    path('customers/', customer, name='customers'),
    path('customer/account/<int:customer_id>/', customer_account, name='customer'),
    path('customer/add/', customer, name='add_customer'),
    
    #currency
    path('currency/', currency, name='currency'),
    path('currency/json', currency_json, name='currency_json'),
    path('currency/add/', add_currency, name='add_currency'),
    path('currency/update/<int:currency_id>/', update_currency, name='update_currency'),
    path('currency/delete/<int:currency_id>/', delete_currency, name='delete_currency'),
    
    #settings
    path('settings/', finance_settings, name='finance_settings'),
    
    #reports
    path('expenses-report/', expenses_report, name='expenses_report'),  
]