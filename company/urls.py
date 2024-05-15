from django.urls import path
from . views import *

app_name = 'company'

urlpatterns = [
    path('switch/<int:branch_id>/', branch_switch, name='switch_branch')
]
