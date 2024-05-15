from . models import Branch

def branch_list(request):
    return{'branches':Branch.objects.all()}
    