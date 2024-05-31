from django.views import View
from django.shortcuts import render,redirect
from .models import User
from .forms import UserRegistrationForm
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.hashers import make_password


class usersView(View):
    def get(self, request):
        users = User.objects.all()
        return render(request, 'auth/users', {
            users:users
        })
    

def login_view(request):
    if request.method =='POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(
            request,
            username=username,
            password=password
        )
        if user is not None:
            login(request, user)
            return redirect('pos:pos')
        else: messages.error(request, 'Invalid username or password')
    return render(request, 'auth/login.html')

def register(request):
    form = UserRegistrationForm()
    if request.method =='POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            user=form.save(commit=False)
            user.password=make_password(form.cleaned_data['password'])
            user.save()
            messages.success(request, 'User successfully added')
        else: 
            messages.error(request, 'Error')
    return render(request, 'auth/register.html', {
        'form':form
    })

def logout_view(request):
    logout(request)
    return redirect('users:login')
