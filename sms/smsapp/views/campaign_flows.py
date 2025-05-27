from ..models import Flows
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from ..models import Templates
import requests
from django.contrib import messages
import json
from ..functions.template_msg import fetch_templates
from ..functions.flows import get_flows,create_message_template_with_flow
from ..functions.send_messages import display_phonenumber_id
from ..utils import CustomJSONDecoder, get_token_and_app_id, display_whatsapp_id, logger
from .auth import username




@login_required
def create_flow_message(request):
    token, _ = get_token_and_app_id(request)
    waba_id = display_whatsapp_id(request)

    flows = get_flows(token, waba_id)
    local_db_flows = Flows.objects.filter(email=request.user)
    flow_value = list(local_db_flows.values_list('flows', flat=True))
    filtered_flows = [flow for flow in flows if flow['name'] in flow_value] if flow_value else []
        
    if request.method == 'POST':
        # Retrieve form data from POST request
        flow_name = request.POST.get('name')
        category = request.POST.get('category')
        json_flow = request.POST.get('json_flow')

        flow_data = json.loads(json_flow, cls=CustomJSONDecoder)

        try:
            response = create_flow(token, waba_id, flow_name, category, flow_data)
            if response.status_code == 200:
                Flows.objects.create(email=request.user, flows=flow_name)
                messages.success(request, "Flow Created Successfully")
            else:
                messages.error(request, f"Failed to create flow template {response.json()}")
        except Exception as e:
            messages.error(request, "Failed to create flow template")
            logger.error(f"Couldn't create flow template {e}")

    context = {
        "flows": filtered_flows,
        "coins":request.user.marketing_coins + request.user.authentication_coins,
        "marketing_coins":request.user.marketing_coins,
        "authentication_coins":request.user.authentication_coins,
        "username": username(request),
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request),
    }

    return render(request, "create_flow_template.html", context)


@login_required
@csrf_exempt
def publish_flow(request, flow_id):
    ACCESS_TOKEN, _ = get_token_and_app_id(request)
    BASE_URL = 'https://graph.facebook.com/v20.0'
    url = f"{BASE_URL}/{flow_id}/publish"
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers)
        
        if response.status_code == 200:
            return JsonResponse({
                'success': True,
                'message': f'Flow "{flow_id}" successfully published'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': f'Failed to publish flow. Status code: {response.status_code}'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error publishing flow: {str(e)}'
        })

@login_required
@csrf_exempt
def deprecate_flow(request, flow_id):
    ACCESS_TOKEN, _ = get_token_and_app_id(request)
    BASE_URL = 'https://graph.facebook.com/v20.0'
    url = f"{BASE_URL}/{flow_id}/deprecate"
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers)
        
        if response.status_code == 200:
            return JsonResponse({
                'success': True,
                'message': f'Flow "{flow_id}" successfully deprecated'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': f'Failed to deprecate flow. Status code: {response.status_code}'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error deprecating flow: {str(e)}'
        })

def create_flow(token, waba_id, flow_name, categories, flow_json):
    BASE_URL = 'https://graph.facebook.com/v20.0'
    url = f"{BASE_URL}/{waba_id}/flows"
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    data = {
        "name": flow_name,
        "categories": categories
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        flow_id = response.json().get('id')
        response = update_flow_json(BASE_URL, flow_id, flow_name, token, flow_json)
        return response
    else:
        return response


def update_flow_json(base_url, flow_id, flow_name, access_token, flow_json):
    url = f"{base_url}/{flow_id}/assets"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    
    files = {
        'file': ('flow.json', json.dumps(flow_json), 'application/json'),
        'name': (None, 'flow.json'),
        'asset_type': (None, 'FLOW_JSON')
    }

    response = requests.post(url, headers=headers, files=files)
    
    if response.status_code == 200:
        return response
    else:
        return False

@login_required
@csrf_exempt
def delete_flow(request, flow_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    ACCESS_TOKEN, _ = get_token_and_app_id(request)
    BASE_URL = 'https://graph.facebook.com/v20.0'
    
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}'
    }
    
    try:
        # First, get the flow details to find its name
        flow_details_url = f"{BASE_URL}/{flow_id}"
        flow_response = requests.get(flow_details_url, headers=headers)
        
        if flow_response.status_code != 200:
            return JsonResponse({
                'success': False,
                'message': f'Failed to get flow details. Status code: {flow_response.status_code}'
            })
            
        flow_name = flow_response.json().get('name')
        if not flow_name:
            return JsonResponse({
                'success': False,
                'message': 'Could not find flow name'
            })
        
        # Delete from Facebook
        delete_url = f"{BASE_URL}/{flow_id}"
        response = requests.delete(delete_url, headers=headers)
        
        try:
            flow = Flows.objects.get(email=request.user, flows=flow_name)
            flow.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Flow successfully deleted from Facebook and database'
            })
        except Flows.DoesNotExist:
            return JsonResponse({
                'success': True,
                'message': 'Flow deleted from Facebook but not found in database'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error deleting flow: {str(e)}'
        })
        
@login_required
@csrf_exempt
def delete_flow(request, flow_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    ACCESS_TOKEN, _ = get_token_and_app_id(request)
    BASE_URL = 'https://graph.facebook.com/v20.0'
    
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}'
    }
    
    try:
        # First, get the flow details to find its name
        flow_details_url = f"{BASE_URL}/{flow_id}"
        flow_response = requests.get(flow_details_url, headers=headers)
        
        if flow_response.status_code != 200:
            return JsonResponse({
                'success': False,
                'message': f'Failed to get flow details. Status code: {flow_response.status_code}'
            })
            
        flow_name = flow_response.json().get('name')
        if not flow_name:
            return JsonResponse({
                'success': False,
                'message': 'Could not find flow name'
            })
        
        # Delete from Facebook
        delete_url = f"{BASE_URL}/{flow_id}"
        response = requests.delete(delete_url, headers=headers)
        
        try:
            flow = Flows.objects.get(email=request.user, flows=flow_name)
            flow.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Flow successfully deleted from Facebook and database'
            })
        except Flows.DoesNotExist:
            return JsonResponse({
                'success': True,
                'message': 'Flow deleted from Facebook but not found in database'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error deleting flow: {str(e)}'
        })
    
def get_preview_url(request, flow_id):
    # Define the URL
    BASE_URL = 'https://graph.facebook.com/v20.0'
    token, _ = get_token_and_app_id(request)
    ACCESS_TOKEN = token
    url = f"{BASE_URL}/{flow_id}?fields=preview.invalidate(false)"

    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}'
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        logger.info("Flow Request successful!")
        data = response.json()
        return data['preview']['preview_url']
    else:
        logger.error(f"Request failed. Status code: {response.status_code} {response.text}")
        return None
    
def get_preview_url_view(request, flow_id):
    preview_url = get_preview_url(request, flow_id)
    if preview_url:
        return JsonResponse({'preview_url': preview_url})
    else:
        return JsonResponse({'error': 'Failed to fetch preview URL'}, status=400)
    
@csrf_exempt
def create_template_from_flow(request):
    token, _ = get_token_and_app_id(request)
    waba_id = display_whatsapp_id(request)
    if request.method == 'POST':
        flow_id = request.POST.get('flow_id')
        template_name = request.POST.get('template_name')
        category = request.POST.get('category')
        body_text = request.POST.get('body_text')
        lang = request.POST.get('lang')
        flow_button = request.POST.get('flow_button')

        response = create_message_template_with_flow(
            waba_id, body_text, lang, category, token, template_name, flow_id, str(flow_button)
        )
        
        if response:
            messages.success(request, "Flow Template created successfully")
            try:
                Templates.objects.create(email=request.user, templates=template_name)
            except Exception as e:
                logger.error(f"Error, {e}")
            return JsonResponse({'success': True})
        
        else:
            logger.error("Failed to crate Flow Template")
            messages.error(request, "Failed to crate Flow Template")
            return JsonResponse({'success': False, 'error': 'Failed to create template'})