from django.shortcuts import render, redirect, get_object_or_404
from . models import Branch, Company
from permissions import permissions
from django.contrib import messages
from .forms import BranchForm

def branch_list(request):
    branches = Branch.objects.all()
    return render(request, 'branches/branches.html', {'branches':branches})

def branch_switch(request, branch_id):
    user = request.user
    if user.role == 'Admin' or user.role == 'admin':
        user.branch = Branch.objects.get(id=branch_id)
        user.save()
    else: messages.error(request, 'You are not authorized')
    return redirect('pos:pos')


# @permissions(['Admin'])  
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
