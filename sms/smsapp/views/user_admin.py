import psutil
import time
from datetime import datetime, timedelta
from collections import deque
import threading
import statistics
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Sum
from django.utils.timezone import make_aware
from django.shortcuts import render
from .auth import admin_check
from ..models import CoinsHistory, LoginHistory
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

# Global variables to track CPU usage history
cpu_history = deque(maxlen=300)  # Store 5 minutes of data at 1-second intervals
cpu_history_lock = threading.Lock()
monitoring_thread = None
is_monitoring = False

def start_cpu_monitoring():
    """Start a background thread to monitor CPU usage"""
    global monitoring_thread, is_monitoring
    
    if is_monitoring:
        return  # Already monitoring
    
    is_monitoring = True
    
    def monitor_cpu():
        while is_monitoring:
            with cpu_history_lock:
                cpu_history.append((datetime.now(), psutil.cpu_percent(interval=1)))
    
    monitoring_thread = threading.Thread(target=monitor_cpu)
    monitoring_thread.daemon = True  # Thread will exit when main program exits
    monitoring_thread.start()

def stop_cpu_monitoring():
    """Stop the CPU monitoring thread"""
    global is_monitoring
    is_monitoring = False
    if monitoring_thread:
        monitoring_thread.join(timeout=2)

def get_cpu_history_stats(minutes=5):
    """Get statistics about CPU usage over the specified period"""
    with cpu_history_lock:
        if not cpu_history:
            return {
                'current': 0,
                'average': 0,
                'max': 0,
                'min': 0,
                'above_90_percent': False,
                'samples_count': 0,
                'high_samples_count': 0
            }
        
        # Get samples from the last X minutes
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        recent_samples = [usage for timestamp, usage in cpu_history if timestamp >= cutoff_time]
        
        if not recent_samples:
            current = cpu_history[-1][1] if cpu_history else 0
            return {
                'current': current,
                'average': 0,
                'max': 0,
                'min': 0,
                'above_90_percent': False,
                'samples_count': 0,
                'high_samples_count': 0
            }
        
        # Calculate statistics
        high_samples = [s for s in recent_samples if s >= 90]
        
        return {
            'current': cpu_history[-1][1] if cpu_history else 0,
            'average': statistics.mean(recent_samples),
            'max': max(recent_samples),
            'min': min(recent_samples),
            'above_90_percent': len(high_samples) / len(recent_samples) >= 0.8,
            'samples_count': len(recent_samples),
            'high_samples_count': len(high_samples)
        }

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
    coins_history = CoinsHistory.objects.all()
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

# Add this to your app's initialization code (e.g., in apps.py or a suitable place)
def initialize_monitoring():
    start_cpu_monitoring()

# Add this to your app's shutdown code (e.g., signal handlers)
def cleanup_monitoring():
    stop_cpu_monitoring()