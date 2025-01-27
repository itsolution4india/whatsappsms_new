from django.utils import timezone
from django.contrib.auth import logout
import logging
from django.shortcuts import redirect

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

class AutoLogoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            last_activity = request.session.get('last_activity')
            if last_activity:
                inactive_duration = timezone.now() - last_activity
                if inactive_duration.total_seconds() > 900:  # 15 minutes
                    logout(request)
                    return redirect('login')
            request.session['last_activity'] = timezone.now()
        response = self.get_response(request)
        return response