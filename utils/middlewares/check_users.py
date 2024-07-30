from django.contrib.auth import get_user_model
from django.shortcuts import redirect
import logging

logger = logging.getLogger(__name__)

class CheckUsersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
   
    def __call__(self, request):
        logger.info(f'Request-> {request}')
        User = get_user_model()
        if not User.objects.exists() and request.path != '/company/register-company/':
            logger.info(f'Request->  redirected')
            return redirect('company:register-company')
        return redirect('users:users')
