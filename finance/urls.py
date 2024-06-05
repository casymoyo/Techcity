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
    path('expenses/confirm/<int:expense_id>/', confirm_expense, name='confirm_expense'),  
    path('expense/category/add', create_expense_category, name='create_expense_category' ),
    
    #invoice
    path('invoice/', invoice, name='invoice'),
    path('invoice/pdf/', invoice_pdf, name='invoice_pdf'),
    path('invoice/create/', create_invoice, name='create_invoice'),
    path('invoice/payments/', invoice_payment_track, name='payments'),
    path('invoice/delete/<int:invoice_id>/', delete_invoice, name='delete_invoice'),
    path('invoice/update/<str:invoice_id>/', update_invoice, name='update_invoice'),
    path('invoice/details/<int:invoice_id>/', invoice_details, name='invoice_details'),
    path('invoice/preview/<int:invoice_id>/', invoice_preview, name='invoice_preview'),
    
    #customer
    path('customers/', customer, name='customers'),
    path('customer/add/', customer, name='add_customer'),
    path('customers/list/', customer_list, name='customer_list'),
    path('customer/account/<int:customer_id>/', customer_account, name='customer'),
    path('customers/update/<int:customer_id>/', update_customer, name='update_customer'),
    path('customer/delete/<int:customer_id>/delete/', delete_customer, name='customer_delete'),
    path('customer/payments/json/', customer_account_payments_json, name='customer_payments_json'),
    path('customer/account/json/<int:customer_id>/', customer_account_json, name='customer_account_json'),
    path('customer/transactions/json/', customer_account_transactions_json, name='customer_transactions_json'),
    
    #currency
    path('currency/', currency, name='currency'),
    path('currency/json', currency_json, name='currency_json'),
    path('currency/add/', add_currency, name='add_currency'),
    path('currency/update/<int:currency_id>/', update_currency, name='update_currency'),
    path('currency/delete/<int:currency_id>/', delete_currency, name='delete_currency'),
    
    path('analytics/', analytics, name='analytics'),
    
    # end of day
    path('end_of_day/', end_of_day, name='end_of_day'),
    
    #settings
    path('settings/', finance_settings, name='finance_settings'),
    
    #reports
    path('expenses-report/', expenses_report, name='expenses_report'),  
    
    #email
    path('invoice/send/email/', send_invoice_email, name='invoice_email'),
    path('send_invoice_whatsapp/<int:invoice_id>/', send_invoice_whatsapp, name='send_invoice_whatsapp'),
    # path('invoice/email/status/<str:task_id>/', check_email_task_status, name='email_status')
]