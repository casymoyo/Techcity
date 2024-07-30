from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect, get_object_or_404

from users.models import User
from .models import Branch, Company
from permissions import permissions
from django.contrib import messages
from .forms import BranchForm

def registration(request):
    return render(request, 'company/registration.html')

def register_company_view(request):
    """
    payload = {
        'company_data' : {},
        'user_data': {}
    }
    """
    payload = request.data
    if request.method == 'POST':
        try:
            # with atomic
            # validate json data
            # under try block

            # create company
            company_data = payload.data['company_data']
            company = Company(
                name=company_data['name'],
                description=company_data['description'],
                address=company_data['address'],
                domain=company_data['domain'],
                logo=company_data['logo'],
                email=company_data['email'],
                phone_number=company_data['phone_number'],
            ).save()

            user_role = 'owner'

            # create user (user is owner)
            user_data = payload.data['user_data']
            user = User()
            user.first_name = user_data['first_name']
            user.last_name = user_data['last_name']
            user.username = user_data['user_name']
            user.email = user_data['email']
            user.company = company.name
            user.phonenumber = user_data['phonenumber']
            user.role = user_role
            user.password = make_password(user_data['password'])
            user.save()

            # return message
            messages.success(request, 'Company registration successful!')
        except Exception as e:
            messages.success(request, 'Error creating company')

def branch_list(request):
    branches = Branch.objects.all()
    return render(request, 'branches/branches.html', {'branches': branches})


def branch_switch(request, branch_id):
    user = request.user
    if user.role == 'Admin' or user.role == 'admin':
        user.branch = Branch.objects.get(id=branch_id)
        user.save()
    else:
        messages.error(request, 'You are not authorized')
    return redirect('pos:pos')


def add_branch(request):
    if request.method == 'POST':
        form = BranchForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Branch added successfully!')
            return redirect('company:branch_list')
    else:
        form = BranchForm()
    return render(request, 'branches/add_branch.html', {'form': form})


# @permissions(['Admin'])
def edit_branch(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if request.method == 'POST':
        form = BranchForm(request.POST, instance=branch)
        if form.is_valid():
            form.save()
            messages.success(request, 'Branch updated successfully!')
            return redirect('company:branch_list')
    else:
        form = BranchForm(instance=branch)
    return render(request, 'branches/edit_branch.html', {'form': form, 'branch': branch})
