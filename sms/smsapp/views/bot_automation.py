from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from ..models import Templates, MessageResponse
import json
from django.db import IntegrityError
from ..functions.template_msg import fetch_templates
from ..functions.send_messages import display_phonenumber_id
from ..utils import get_token_and_app_id, display_whatsapp_id, logger
from .auth import username, check_user_permission
from django.views.decorators.csrf import csrf_exempt


@login_required
def bot_flow(request):
    # Early permission check
    if not check_user_permission(request.user, 'can_manage_bot_flow'):
        return redirect("access_denide")  # Note: There's a typo in "denied"
    
    # Handle POST requests first to avoid unnecessary database queries for POST operations
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_response = data.get('user_response')
            message_type = data.get('message_type')

            # Check for duplicate response using a more efficient query
            if MessageResponse.objects.filter(user=request.user, user_response=user_response).exists():
                return JsonResponse({
                    'status': 'error',
                    'message': 'This response has already been used. Please use a different response.'
                }, status=400)

            # Create message response object but don't save yet
            message_response = MessageResponse(
                user=request.user,
                message_type=message_type,
                user_response=user_response,
                body_message=data.get('body_message', '')
            )

            # Conditionally set fields only if they exist in the data
            optional_fields = ['sections', 'buttons', 'product_section']
            for field in optional_fields:
                if data.get(field):
                    setattr(message_response, field, data[field])

            # Handle specific message types in a more structured way
            if message_type == 'send_my_location':
                message_response.latitude = data['product_data']['mylatitude']
                message_response.longitude = data['mylongitude']
            elif message_type in ['single_product_message', 'multi_product_message']:
                product_data = data.get('product_data', {})
                message_response.product_retailer_id = product_data.get('product_retailer_id')
                message_response.catalog_id = data.get('catalog_id')
            elif message_type == 'link_template':
                product_data = data.get('product_data', {})
                message_response.template_name = product_data.get('selectedTempale')
                message_response.catalog_id = data.get('catalog_id')

            # Save with exception handling
            try:
                message_response.save()
                return JsonResponse({
                    'status': 'success',
                    'message': 'Configuration saved successfully',
                    'data': {
                        'user_response': user_response,
                        'message_type': message_type
                    }
                })
            except IntegrityError:
                logger.warning(f"Duplicate response attempt for user {request.user.id}: {user_response}")
                return JsonResponse({
                    'status': 'error',
                    'message': 'This response has already been used. Please use a different response.'
                }, status=400)
        except Exception as e:
            logger.error(f"Error in bot_flow POST for user {request.user.id}: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    # For GET requests, process template data
    token, app_id = get_token_and_app_id(request)
    
    # Fetch user-specific template values first (database query)
    template_database = Templates.objects.filter(email=request.user)
    template_value = set(template_database.values_list('templates', flat=True))  # Using set for O(1) lookups
    
    # Fetch campaign list (likely API call)
    campaign_list = fetch_templates(display_whatsapp_id(request), token) or []
    
    # Filter templates with a list comprehension (more efficient than multiple conditionals)
    templates = [campaign for campaign in campaign_list if campaign['template_name'] in template_value]
    
    # Fetch bot automation in a single query
    bot_automation = MessageResponse.objects.filter(user=request.user)
    
    # Extract template data once
    template_names = [template['template_name'] for template in templates]
    template_data = [template['template_data'] for template in templates]
    template_status = [template['status'] for template in templates]
    template_button = [json.dumps(template['button']) for template in templates]
    template_media = [template.get('media_type', 'No media available') for template in templates]
    
    # Build context dictionary efficiently
    context = {
        "current_user": request.user,
        "bot_automation": bot_automation,
        "template_names": template_names,
        "coins": request.user.marketing_coins + request.user.authentication_coins,
        "marketing_coins": request.user.marketing_coins,
        "authentication_coins": request.user.authentication_coins,
        "username": username(request),
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request),
        "template_name": template_names,
        "template_data": json.dumps(template_data),
        "template_status": json.dumps(template_status),
        "template_button": json.dumps(template_button),
        "template_media": json.dumps(template_media),
    }
    
    return render(request, "bot-flow.html", context)

@login_required
@csrf_exempt  # This is necessary for DELETE requests in some setups
def delete_message(request, message_id):
    if request.method == 'DELETE':
        try:
            # Fetch the message to be deleted
            message = MessageResponse.objects.get(id=message_id, user=request.user)
            
            # Delete the message
            message.delete()

            return JsonResponse({
                'status': 'success',
                'message': 'Message deleted successfully.'
            })
        except MessageResponse.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Message not found.'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method.'
    }, status=405)