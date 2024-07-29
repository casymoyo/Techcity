from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Q
from django.http import JsonResponse
from django.views import View
from django.shortcuts import render, redirect
from loguru import logger

from company.models import Branch
from utils.authenticate import authenticate_user
from .models import User
from .forms import UserRegistrationForm, UserDetailsForm, UserDetailsForm2
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.hashers import make_password


def users(request):
    search_query = request.GET.get('q', '')
    users = User.objects.filter(Q(username__icontains=search_query) | Q(email__icontains=search_query)).order_by(
        'first_name', 'last_name')
    form = UserRegistrationForm()
    user_details_form = UserDetailsForm2()

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            user = form.save(commit=False)
            user.password = make_password(form.cleaned_data['password'])
            user.save()
            messages.success(request, 'User successfully added')
        else:
            messages.error(request, 'Invalid form data')

    return render(request, 'auth/users.html', {'users': users, 'form': form, 'user_details_form': user_details_form})


def login_view(request):
    if request.method == 'POST':
        email_address = request.POST['email_address']
        password = request.POST['password']

        # Validate email
        try:
            validate_email(email_address)
        except ValidationError:
            messages.error(request, 'Invalid email format')
            return render(request, 'auth/login.html')

        # todo allow authentication to verified email addresses
        user = authenticate_user(email=email_address, password=password)
        logger.info(f'User: {user}')
        if user is not None:
            if user.is_active:
                login(request, user)
                return redirect('pos:pos')
            else:
                messages.error(request, 'Your account is not active, contact admin')
        else:
            messages.error(request, 'Invalid username or password')
    return render(request, 'auth/login.html', )


def user_edit(request, user_id):
    user = User.objects.get(id=user_id)
    logger.info(f'User details: {user.first_name + " " + user.email}')
    if request.method == 'POST':
        form = UserDetailsForm2(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'User details updated successfully')
            return redirect('users:user_detail', user_id=user.id)
        else:
            messages.error(request, 'Invalid form data')
    else:
        form = UserDetailsForm2(instance=user)
    return render(request, 'auth/users.html', {'user': user, 'form': form})


def user_detail(request, user_id):
    user = User.objects.get(id=user_id)
    form = UserDetailsForm()

    logger.info(f'User details: {user.first_name + " " + user.email}')
    # render user details
    if request.method == 'GET':
        return render(request, 'users/user_detail.html', {'user': user, 'form': form})
    if request.method == 'POST':
        form = UserDetailsForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'User details updated successfully')
        else:
            messages.error(request, 'Invalid form data')
        return render(request, 'users/user_detail.html', {'user': user, 'form': form})


def register(request):
    form = UserRegistrationForm()
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            user = form.save(commit=False)
            user.password = make_password(form.cleaned_data['password'])
            user.save()
            messages.success(request, 'User successfully added')
        else:
            messages.error(request, 'Error')
    return render(request, 'auth/register.html', {
        'form': form
    })


def load_branches(request):
    """
    we use this view to load branches using js
    """
    company_id = request.GET.get('company_id')
    branches = Branch.objects.filter(company_id=company_id).order_by('name')
    logger.info(f'Branches: {branches.values("id", "name")}')
    return JsonResponse(list(branches.values('id', 'name')), safe=False)


def get_user_data(request, user_id):
    user = User.objects.get(id=user_id)
    user_data = {
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'username': user.username,
        'phonenumber': user.phonenumber,
        'company': user.company.id if user.company else None,
        'branch': user.branch.id if user.branch else None,
        'role': user.role,
    }
    logger.info(f'User data: {user_data}')
    return JsonResponse(user_data)


def logout_view(request):
    logout(request)
    return redirect('users:login')
