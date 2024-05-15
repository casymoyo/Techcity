from django.shortcuts import render, redirect
from . models import Branch, Company
from permissions import permissions
from django.contrib import messages

def branch_switch(request, branch_id):
    user = request.user
    if user.role == 'Admin' or user.role == 'admin':
        user.branch = Branch.objects.get(id=branch_id)
        user.save()
    else: messages.error(request, 'You are not authorized')
    return redirect('pos:pos')


