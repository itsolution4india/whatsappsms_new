import json, requests
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from ..models import Templates, CoinsHistory, ReportInfo, Notifications, LoginHistory
from .auth import username, admin_check
from ..utils import display_whatsapp_id, display_phonenumber_id, logger
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET
import re
from datetime import datetime
from django.contrib.sessions.models import Session
from django.contrib.auth import get_user_model
import psutil
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.decorators import user_passes_test

CustomUser = get_user_model()

def custom_500(request, exception=None):
    return render(request, 'error.html', status=500)

def facebook_sdk_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            code = data.get('code')

            # Step 1: Exchange code for access token
            params = {
                'client_id': '490892730652855',  # Replace with your Facebook App ID
                'client_secret': '2a272b5573130b915db4bccc27caa34f',  # Replace with your Facebook App Secret
                'code': code,
                'redirect_uri': 'https://developers.facebook.com/apps/490892730652855/'
            }
            response = requests.get('https://graph.facebook.com/v20.0/oauth/access_token', params=params)
            logger.info(response.json())
            token_data = response.json()

            if 'access_token' not in token_data:
                return JsonResponse({'error': 'Failed to retrieve access token'}, status=400)

            access_token = token_data['access_token']

            # Step 2: Debug the access token
            debug_params = {
                'input_token': access_token,
                'access_token': 'EAAGZBdt7VWLcBO8nr7i8nChTcNXzWF9aNMjPYVjjKU7BbNfIJGETpZAJY3A2y9vLxzo4xZCace1xKiqG7jS7772Hpak96BPl360cG8Dzt83ujr8BSwGyUbNRS2mIjwZBfUwhNFKXtpFZC2QJ9Lh6OcKLRuoNJ1sAXGk2LZBkNu9BN7JSpBbTnU2vR6neoYv4FFUwZDZD'  # Replace with your Facebook App Access Token
            }
            debug_response = requests.get('https://graph.facebook.com/v20.0/debug_token', params=debug_params)
            debug_data = debug_response.json()
            logger.info(f"debug_data {debug_data}")

            if 'error' in debug_data:
                return JsonResponse({'error': debug_data['error']['message']}, status=400)

            # Step 3: Subscribe WhatsApp Business Account to an application
            waba_id =data.get('waba_id') # Replace with your WhatsApp Business Account ID
            logger.info(f"waba_id, {waba_id}")
            subscribe_endpoint = f'https://graph.facebook.com/v20.0/{waba_id}/subscribed_apps'
            subscribe_params = {
                'subscribed_fields': 'messages, messaging_postbacks, messaging_optins, messaging_referrals',  # Adjust fields as per your requirements
                'access_token': 'EAAGZBdt7VWLcBO8nr7i8nChTcNXzWF9aNMjPYVjjKU7BbNfIJGETpZAJY3A2y9vLxzo4xZCace1xKiqG7jS7772Hpak96BPl360cG8Dzt83ujr8BSwGyUbNRS2mIjwZBfUwhNFKXtpFZC2QJ9Lh6OcKLRuoNJ1sAXGk2LZBkNu9BN7JSpBbTnU2vR6neoYv4FFUwZDZD'  # Replace with your Business Integration System Token
            }
            subscribe_response = requests.post(subscribe_endpoint, params=subscribe_params)
            subscribe_data = subscribe_response.json()

            if 'success' in subscribe_data:
                # Retrieve the WABA ID from the session info (example assumes frontend sends WABA ID in JSON)
                waba_id = data.get('waba_id')
                logger.info(f"success waba_id {waba_id}")
                

                
                return JsonResponse({'message': 'WhatsApp Business Account subscribed successfully', 'waba_id': waba_id})
            elif 'error' in subscribe_data:
                return JsonResponse({'error': subscribe_data['error']['message']}, status=400)
            else:
                return JsonResponse({'error': 'Unknown error occurred'}, status=500)

        except json.JSONDecodeError as e:
            return JsonResponse({'error': 'Invalid JSON format in request body'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    elif request.method == 'GET':
        # Return the rendered HTML template for GET requests
        return render(request, 'facebook_sdk.html')

    else:
        # Handle other HTTP methods (shouldn't happen in your case)
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
def coins_history_list(request):
    template_database = Templates.objects.filter(email=request.user)
    template_value = list(template_database.values_list('templates', flat=True))
    coins_history = CoinsHistory.objects.filter(user=request.user).order_by('-created_at')
    context = {
            "template_names": template_value,
            "coins":request.user.marketing_coins + request.user.authentication_coins,
            "marketing_coins":request.user.marketing_coins,
            "authentication_coins":request.user.authentication_coins,
            "username": username(request),
            "WABA_ID": display_whatsapp_id(request),
            "PHONE_ID": display_phonenumber_id(request),
            "coins_history":coins_history
            }
    return render(request, 'coins_history_list.html', context)

@login_required
def access_denide(request):
    return render(request, "access_denide.html") 

@csrf_exempt
def notify_user(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            logger.info(f"Received notification: {data}")
            status = data.get('status')
            unique_id = data.get('unique_id')
            report_id = data.get('report_id')
            request_id = str(report_id)
            if status == 'completed' and unique_id and request_id:
                if request_id.startswith("MESSAGE") or request_id.startswith("FLOW") or request_id.startswith("CAROUSEL"):
                    try:
                        notification_instance = get_object_or_404(Notifications, request_id=request_id)
                        notification_instance.end_request_id = unique_id
                        notification_instance.save()
                        logger.info(f"Updated response {request_id} with unique_id {unique_id} in end_request_id")
                    except Exception as e:
                        logger.error(f"Failed to update Message end_request_id {str(e)}")
                else:
                    report_instance = get_object_or_404(ReportInfo, id=report_id)

                    report_instance.end_request_id = unique_id
                    report_instance.save()

                    logger.info(f"Updated report {report_id} with unique_id {unique_id} in end_request_id")

                return JsonResponse({"status": "success", "message": "Notification processed successfully"})
            else:
                return JsonResponse({"status": "error", "message": "Invalid data in notification"}, status=400)
        
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON: {e} {request}")
            return JsonResponse({"status": "error", "message": f"Failed to decode notification: {e}"}, status=400)
        except Exception as e:
            logger.error(f"Error processing notification: {e} {request}")
            return JsonResponse({"status": "error", "message": f"Failed to process notification: {e}"}, status=400)
    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=405)

@require_GET
def process_sms_request(request):
    # Get query parameters from the request
    user = request.GET.get('user')
    authkey = request.GET.get('authkey')
    sender = request.GET.get('sender')
    mobile = request.GET.get('mobile')
    text = request.GET.get('text')
    rpt = request.GET.get('rpt')
    output = request.GET.get('output')
    
    numbers = re.findall(r'\d+', text)
    otp = numbers[0]
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Print the extracted values
    logger.info(f"Time: {current_time}, Response: {user}, {authkey}, {sender}, {mobile}, {rpt}, {output}, {otp}")

    if otp:
        # Prepare the API URL with the extracted values
        api_url = f"http://103.104.73.186/api/pushsms?user={user}&authkey={authkey}&sender={sender}&mobile={mobile}&text=Dear+User%2C+%0A+Your+Login+One+Time+Password+is+{otp}%0A+KGVNNT&rpt={rpt}&output={output}"

        try:
            # Call the external API
            response = requests.get(api_url)

            # Log the API response
            logger.info(f"API Response: {response.text}")

            # Return a success response
            return JsonResponse({
                'status': 'success',
                'message': 'SMS sent successfully'
            })
        except requests.RequestException as e:
            logger.error(f"Error calling the API: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to send SMS',
                'error': str(e)
            })
    else:
        return JsonResponse({
            'status': 'error',
            'message': 'OTP not found in the text'
        })

@user_passes_test(admin_check)
def system_status(request):
    cpu_usage = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    total_memory = memory_info.total / (1024 * 1024)
    used_memory = memory_info.used / (1024 * 1024)
    memory_usage_percent = memory_info.percent
    
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
    }

    return render(request, 'system_status.html', context)