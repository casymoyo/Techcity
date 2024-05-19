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
    
    #customer
    path('customers/', customer, name='customers'),
    path('customer/add/', customer, name='add_customer'),
    
    #reports
    path('expenses-report/', expenses_report, name='expenses_report'),  
]