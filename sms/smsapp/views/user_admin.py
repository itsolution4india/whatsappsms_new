import psutil
import os
from datetime import datetime, timedelta
from collections import deque
from django.http import JsonResponse, FileResponse
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Sum
from django.utils.timezone import make_aware
from django.shortcuts import render, redirect
from .auth import admin_check
from ..models import CoinsHistory, LoginHistory
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import json
from django.contrib import messages

CustomUser = get_user_model()

LOG_FILE_PATH = os.path.join(settings.BASE_DIR, 'logs', 'error.log')

@user_passes_test(admin_check)
def system_status(request):
    cpu_usage = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    total_memory = memory_info.total / (1024 * 1024)
    used_memory = memory_info.used / (1024 * 1024)
    memory_usage_percent = memory_info.percent
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    user = request.GET.get('user')
    if not start_date:
        start_date = "2024-12-20"
    
    today = datetime.now().date()
    coins_history = CoinsHistory.objects.filter(type=CoinsHistory.DEBIT)
    if start_date:
        start_date = make_aware(datetime.strptime(start_date, '%Y-%m-%d'))
        coins_history = coins_history.filter(created_at__gte=start_date)

    # Filter by end date if provided
    if end_date:
        end_date = make_aware(datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1))  # Include the full day
        coins_history = coins_history.filter(created_at__lt=end_date)

    # Filter by user if provided
    if user:
        coins_history = coins_history.filter(user=user)
        
    total_coins_utilized_today = CoinsHistory.objects.filter(created_at__date=today).aggregate(Sum('number_of_coins'))['number_of_coins__sum'] or 0
    total_coins_available = CoinsHistory.objects.aggregate(Sum('number_of_coins'))['number_of_coins__sum'] or 0
    
    coins_by_date = (
        coins_history
        .values('created_at__date')
        .annotate(total_coins=Sum('number_of_coins'))
        .order_by('created_at__date')
    )
    
    coins_chart_data = {
        'dates': [str(entry['created_at__date']) for entry in coins_by_date],
        'coins_used': [entry['total_coins'] for entry in coins_by_date],
    }
    
    users = CoinsHistory.objects.values_list('user', flat=True).distinct()
    
    active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
    user_ids = []
    for session in active_sessions:
        data = session.get_decoded()
        user_id = data.get('_auth_user_id', None)
        if user_id:
            user_ids.append(user_id)

    active_users = CustomUser.objects.filter(id__in=user_ids, last_login__gte=timezone.now() - timedelta(minutes=30))
    
    user_login_data = []
    for user in active_users:
        try:
            latest_login = LoginHistory.objects.filter(user=user).latest('login_time')
            user_login_data.append({
                'email': user.email,
                'username': user.username,
                'last_login': latest_login.login_time,
                'ip_address': latest_login.ip_address,
                'location': latest_login.location
            })
        except LoginHistory.DoesNotExist:
            user_login_data.append({
                'email': user.email,
                'username': user.username,
                'last_login': user.last_login,
                'ip_address': 'Unknown',
                'location': 'Unknown'
            })

    disk_usage = psutil.disk_usage('/')
    total_disk = disk_usage.total / (1024 * 1024 * 1024)
    used_disk = disk_usage.used / (1024 * 1024 * 1024)
    free_disk = disk_usage.free / (1024 * 1024 * 1024)
    disk_usage_percent = disk_usage.percent
    net_io = psutil.net_io_counters()
    bytes_sent = net_io.bytes_sent / (1024 * 1024)
    bytes_recv = net_io.bytes_recv / (1024 * 1024)

    uptime_seconds = (datetime.now() - datetime.fromtimestamp(psutil.boot_time())).total_seconds()
    uptime = str(timedelta(seconds=uptime_seconds))

    running_processes = len(psutil.pids())

    load_averages = psutil.getloadavg()

    context = {
        'cpu_usage': cpu_usage,
        'total_memory': total_memory,
        'used_memory': used_memory,
        'memory_usage_percent': memory_usage_percent,
        'total_disk': total_disk,
        'used_disk': used_disk,
        'free_disk': free_disk,
        'disk_usage_percent': disk_usage_percent,
        'bytes_sent': bytes_sent,
        'bytes_recv': bytes_recv,
        'uptime': uptime,
        'running_processes': running_processes,
        'load_averages': load_averages,
        'user_login_data': user_login_data,
        'coins_chart_data': coins_chart_data,
        'total_coins_utilized_today': total_coins_utilized_today,
        'total_coins_available': total_coins_available,
        'users': users,
        'selected_user': user,
        'selected_start_date': start_date,
        'selected_end_date': end_date,
    }

    return render(request, 'system_status.html', context)

@user_passes_test(admin_check)
def display_logs(request):
    """
    Display the logs with a text editor interface
    """
    # Check if the logs file exists
    if os.path.exists(LOG_FILE_PATH):
        try:
            # Read the logs file content with utf-8 encoding
            with open(LOG_FILE_PATH, 'r', encoding='utf-8') as log_file:
                logs_content = log_file.read()
        except UnicodeDecodeError:
            # If utf-8 decoding fails, try with latin-1 encoding which can handle any byte value
            try:
                with open(LOG_FILE_PATH, 'r', encoding='latin-1') as log_file:
                    logs_content = log_file.read()
            except Exception as e:
                logs_content = f"Error reading logs: {str(e)}"
        except Exception as e:
            logs_content = f"Error reading logs: {str(e)}"
    else:
        logs_content = ""  # Empty string for a new file
    
    context = {'logs': logs_content}
    return render(request, 'display_logs.html', context)

@user_passes_test(admin_check)
@csrf_exempt
def save_logs(request):
    """
    Save edited log content
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            log_content = data.get('content', '')
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
            
            # Save the log content
            with open(LOG_FILE_PATH, 'w', encoding='utf-8') as log_file:
                log_file.write(log_content)
            
            return JsonResponse({'status': 'success', 'message': 'Logs saved successfully'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

@user_passes_test(admin_check)
def delete_logs(request):
    """
    Delete all logs
    """
    if request.method == 'POST':
        if os.path.exists(LOG_FILE_PATH):
            try:
                # Truncate the log file
                open(LOG_FILE_PATH, 'w').close()
                messages.success(request, "Logs deleted successfully.")
            except Exception as e:
                messages.error(request, f"Error deleting logs: {str(e)}")
        else:
            messages.info(request, "Log file not found.")
        
        # Redirect back to the logs display page after deletion
        return redirect('display_logs')
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

@user_passes_test(admin_check)
def download_logs(request):
    """
    Download the logs file
    """
    if os.path.exists(LOG_FILE_PATH):
        response = FileResponse(open(LOG_FILE_PATH, 'rb'))
        response['Content-Disposition'] = 'attachment; filename="logs.txt"'
        return response
    
    messages.error(request, "Log file not found.")
    return redirect('display_logs')