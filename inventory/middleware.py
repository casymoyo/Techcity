from threading import local

_request = local()

class RequestMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        _request.request = request
        return self.get_response(request)

