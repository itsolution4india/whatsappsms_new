# middleware.py

import logging

logger = logging.getLogger('django.request')

class Log404DetailsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if response.status_code == 404:
            # Log details of the 404 request
            logger.warning(f"404 Not Found: {request.path} - IP: {request.META.get('REMOTE_ADDR')} - User-Agent: {request.META.get('HTTP_USER_AGENT')}")
        
        return response
