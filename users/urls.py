from django.urls import path
from . views import *

app_name='users'

urlpatterns = [
    path('', usersView.as_view() ,name='users'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('register/', register, name='register'),
]
