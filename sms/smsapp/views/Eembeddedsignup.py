from django.shortcuts import render
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests

from dotenv import load_dotenv
import os

load_dotenv()

# Constants (you may want to store these in environment variables)
API_VERSION = os.getenv('API_VERSION')
SYSTEM_TOKEN = os.getenv('SYSTEM_TOKEN')
BUSINESS_PORTFOLIO_ID = os.getenv('BUSINESS_PORTFOLIO_ID')
SUPPORTED_CURRENCIES = os.getenv('SUPPORTED_CURRENCIES')

def signup_view(request):
    return render(request, 'signup.html')

@csrf_exempt
def process_signup(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        access_token = data.get('access_token')
        user_id = data.get('user_id')

        return JsonResponse({'status': 'success', 'message': 'Signup processed successfully'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

def get_credit_line_id(request):
    url = f"https://graph.facebook.com/{API_VERSION}/{BUSINESS_PORTFOLIO_ID}/extendedcredits"
    headers = {
        'Authorization': f'Bearer {SYSTEM_TOKEN}',
    }

    response = requests.get(url, headers=headers)
    
    print(response.json())
    if response.status_code == 200:
        credit_data = response.json().get('data', [])
        if credit_data:
            credit_line_id = credit_data[0].get('id')
            return render(request, 'credit_line_id.html', {'credit_line_id': credit_line_id})
    return JsonResponse({'error': 'Unable to fetch credit line ID'}, status=400)

def share_credit_line(request):
    if request.method == "POST":
        customer_waba_id = request.POST.get('customer_waba_id')
        customer_currency = request.POST.get('customer_currency').upper()  # Ensure currency code is uppercase
        credit_line_id = request.POST.get('credit_line_id')

        # Validate the currency code
        if customer_currency not in SUPPORTED_CURRENCIES:
            return JsonResponse({'error': 'Invalid or unsupported currency code. Supported currencies: AUD, EUR, GBP, IDR, INR, USD.'}, status=400)

        # Make the API request if the currency is valid
        url = f"https://graph.facebook.com/{API_VERSION}/{credit_line_id}/whatsapp_credit_sharing_and_attach?waba_currency={customer_currency}&waba_id={customer_waba_id}"
        headers = {
            'Authorization': f'Bearer {SYSTEM_TOKEN}',
        }

        response = requests.post(url, headers=headers)
        print("response", response.json())

        if response.status_code == 200:
            return JsonResponse({'success': 'Credit line shared successfully!'}, status=200)
        return JsonResponse({'error': 'Failed to share credit line', 'details': response.json()}, status=400)

    return render(request, 'share_credit_line.html')

def get_business_portfolio_id(request, waba_id):
    url = f"https://graph.facebook.com/{API_VERSION}/{waba_id}?fields=owner_business_info"
    headers = {
        'Authorization': f'Bearer {SYSTEM_TOKEN}',
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        business_info = response.json().get('owner_business_info', {})
        business_portfolio_id = business_info.get('id', 'No Business Portfolio ID Found')
        return render(request, 'business_portfolio_id.html', {'business_portfolio_id': business_portfolio_id})
    return JsonResponse({'error': 'Unable to fetch business portfolio ID'}, status=400)

def attach_credit_line(request, extended_credit_line_id, waba_currency, waba_id):
    url = f"https://graph.facebook.com/{API_VERSION}/{extended_credit_line_id}/whatsapp_credit_attach"
    params = {
        'waba_currency': waba_currency,
        'waba_id': waba_id,
    }
    headers = {
        'Authorization': f'Bearer {SYSTEM_TOKEN}',
    }
    
    response = requests.post(url, headers=headers, params=params)
    
    if response.status_code == 200:
        result = response.json()
        return render(request, 'credit_line_attached.html', {'result': result})
    return JsonResponse({'error': 'Unable to attach credit line'}, status=400)

def get_receiving_credential(request, extended_credit_allocation_id):
    url = f"https://graph.facebook.com/{API_VERSION}/{extended_credit_allocation_id}?fields=receiving_credential"
    headers = {
        'Authorization': f'Bearer {SYSTEM_TOKEN}',
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        receiving_credential = response.json().get('receiving_credential', 'No Receiving Credential Found')
        return render(request, 'receiving_credential.html', {'receiving_credential': receiving_credential})
    return JsonResponse({'error': 'Unable to fetch receiving credential'}, status=400)

def get_primary_funding_id(request, waba_id):
    url = f"https://graph.facebook.com/{API_VERSION}/{waba_id}?fields=primary_funding_id"
    headers = {
        'Authorization': f'Bearer {SYSTEM_TOKEN}',
    }
    
    response = requests.get(url, headers=headers)
    print("response", response.json())
    
    if response.status_code == 200:
        primary_funding_id = response.json().get('primary_funding_id', 'No Primary Funding ID Found')
        return render(request, 'primary_funding_id.html', {'primary_funding_id': primary_funding_id})
    return JsonResponse({'error': 'Unable to fetch primary funding ID'}, status=400)