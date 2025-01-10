import json, requests
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from ..models import Templates, CoinsHistory, ReportInfo, Notifications
from .auth import username
from ..utils import display_whatsapp_id, display_phonenumber_id, logger
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

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

    # Print the extracted values
    logger.info(f"user: {user}")
    logger.info(f"authkey: {authkey}")
    logger.info(f"sender: {sender}")
    logger.info(f"mobile: {mobile}")
    logger.info(f"text: {text}")
    logger.info(f"rpt: {rpt}")
    logger.info(f"output: {output}")

    # Optionally return a response if needed
    return JsonResponse({
        'status': 'success',
        'message': 'Data processed successfully'
    })
