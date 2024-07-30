from django.urls import path
from . views import *

app_name = 'company'

urlpatterns = [
    path('register-company/', register_company_view, name='register-company'),
    path('', branch_list, name='branch_list'),
    path('add/', add_branch, name='add_branch'),
    path('edit/<int:branch_id>/', edit_branch, name='edit_branch'),
    path('switch/<int:branch_id>/', branch_switch, name='switch_branch')
]
