from django.utils import timezone
from django.contrib.auth import logout
import logging
from django.shortcuts import redirect
from datetime import datetime
from django.db import close_old_connections
from django.urls import reverse
import traceback


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
                last_activity = datetime.fromisoformat(last_activity)
                inactive_duration = timezone.now() - last_activity
                if inactive_duration.total_seconds() > 900:
                    logout(request)  # Log out the user
                    return redirect('login')  # Redirect to login after logout

            request.session['last_activity'] = timezone.now().isoformat()

        response = self.get_response(request)
        return response
    
class ConnectionCleanupMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        close_old_connections()
        response = self.get_response(request)
        close_old_connections()
        
        return response
    

class ErrorRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)

            # Check for all error codes you want to handle dynamically
            if response.status_code in [400, 401, 403, 404, 405, 408, 500, 502, 503, 504]:
                return redirect(f"{reverse('dynamic_error_view')}?code={response.status_code}")

            return response
        except Exception:
            # Handle any unexpected error as 500
            traceback.print_exc()
            return redirect(f"{reverse('dynamic_error_view')}?code=500")