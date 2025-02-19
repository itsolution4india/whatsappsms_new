from django.shortcuts import render
from django.http import JsonResponse
import requests
import json
from ..utils import display_phonenumber_id, get_token_and_app_id, display_whatsapp_id
from django.contrib.auth.decorators import login_required
from .auth import username

@login_required
def generate_qr_code(request):
    context = {
            "coins": request.user.marketing_coins + request.user.authentication_coins,
            "marketing_coins": request.user.marketing_coins,
            "authentication_coins": request.user.authentication_coins,
            "username": username(request),
            "WABA_ID": display_whatsapp_id(request),
            "PHONE_ID": display_phonenumber_id(request)
        }
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message = data.get('message')
            PHONE_NUMBER_ID = display_phonenumber_id(request)
            FB_TOKEN, _ = get_token_and_app_id(request)
            # Define the URL and headers
            url = f'https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/message_qrdls'
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {FB_TOKEN}'
            }
            
            # Define the payload
            payload = {
                'prefilled_message': message,
                'generate_qr_image': 'SVG'
            }
            
            # Make the POST request
            response = requests.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                return JsonResponse(response.json())
            else:
                return JsonResponse({
                    'error': f'Error: {response.status_code}, {response.text}'
                }, status=400)
                
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return render(request, "generateqr.html", context)