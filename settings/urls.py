from django.urls import path
from . views import *

app_name = 'settings'

urlpatterns = [
    path('', settings, name='settings')
]