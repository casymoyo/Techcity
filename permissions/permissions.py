from django.http import HttpResponseForbidden


def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if request.user.role == 'admin':
            return view_func(request, *args, **kwargs)
        else:
            return HttpResponseForbidden()

    return wrapper


def sales_required(view_func):
    def wrapper(request, *args, **kwargs):
        if request.user.role == 'sales':
            return view_func(request, *args, **kwargs)
        else:
            return HttpResponseForbidden()

    return wrapper


def accountant_required(view_func):
    def wrapper(request, *args, **kwargs):
        if request.user.role == 'accountant':
            return view_func(request, *args, **kwargs)
        else:
            return HttpResponseForbidden()

    return


def allowed_users(allowed_roles={}, default_allowed_methods=['GET']):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            role = request.user.role
            if role not in allowed_roles:
                return HttpResponseForbidden("You are not authorized to view this resource")

            allowed_methods = allowed_roles.get(role, default_allowed_methods)
            if request.method not in allowed_methods:
                return HttpResponseForbidden("Method not allowed")

            return view_func(request, *args, **kwargs)
        return wrapper

    return decorator
