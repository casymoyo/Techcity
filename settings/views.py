import environ
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def settings(request):
    return render(request, 'settings/settings.html')

@login_required
def email_config_view(request):
    """Renders the email configuration form."""
    env = environ.Env()
    environ.Env.read_env()

    initial_data = {
        'EMAIL_HOST': env('EMAIL_HOST'),
        # ... other initial values for the form fields ...
    }
    
    return render(request, 'settings/email_config.html', {'initial_data': initial_data})


@login_required
def save_email_config(request):
    """Handles saving email configuration from the form."""
    if request.method == 'POST':
        env = environ.Env()

        # Update environment variables (.env file)
        for key, value in request.POST.items():
            if key.startswith('EMAIL_'):  
                env(key) = value

        return JsonResponse({'success': True, 'message': 'Email settings updated successfully!'})

    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=400)