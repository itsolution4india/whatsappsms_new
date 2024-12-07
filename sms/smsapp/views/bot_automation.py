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
    if not check_user_permission(request.user, 'can_manage_bot_flow'):
        return redirect("access_denide")
    token, app_id = get_token_and_app_id(request)
    campaign_list = fetch_templates(display_whatsapp_id(request), token)
    template_database = Templates.objects.filter(email=request.user)
    template_value = list(template_database.values_list('templates', flat=True))
    if campaign_list is None:
        campaign_list=[]
    templates = [campaign for campaign in campaign_list if campaign['template_name'] in template_value]

    bot_automation = MessageResponse.objects.filter(user=request.user)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_response = data.get('user_response')
            message_type = data.get('message_type')

            if MessageResponse.objects.filter(user=request.user, user_response=user_response).exists():
                return JsonResponse({
                    'status': 'error',
                    'message': 'This response has already been used. Please use a different response.'
                }, status=400)

            response_data = {
                'user_response': user_response,
                'message_type': message_type
            }

            message_response = MessageResponse(
                user=request.user,
                message_type=message_type,
                user_response=user_response,
                body_message=data.get('body_message', '')
            )

            if data.get('sections'):
                message_response.sections = data['sections']

            if data.get('buttons'):
                message_response.buttons = data['buttons']

            if data.get('productSection'):
                message_response.product_section = data['productSection']

            if message_type == 'send_my_location':
                message_response.latitude = data['product_data']['mylatitude']
                message_response.longitude = data['mylongitude']
            elif message_type in ['single_product_message', 'multi_product_message']:
                message_response.product_retailer_id = data.get('product_data', {}).get('product_retailer_id')
                message_response.catalog_id = data.get('catalog_id')
            elif message_type == 'link_template':
                message_response.template_name = data.get('product_data', {}).get('selectedTempale')
                message_response.catalog_id = data.get('catalog_id')

            try:
                message_response.save()
                return JsonResponse({
                    'status': 'success',
                    'message': 'Configuration saved successfully',
                    'data': response_data
                })
            except IntegrityError:
                logger.warning(f"This response has already been used. Please use a different response.")
                return JsonResponse({
                    'status': 'error',
                    'message': 'This response has already been used. Please use a different response.'
                }, status=400)

        except Exception as e:
            logger.error(f"Error, {e}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    context = {
        "current_user": request.user,
        "bot_automation": bot_automation,
        "template_names": [template['template_name'] for template in templates],
        "coins":request.user.marketing_coins + request.user.authentication_coins,
        "marketing_coins":request.user.marketing_coins,
        "authentication_coins":request.user.authentication_coins,
        "username": username(request),
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request),
        "template_name": [template['template_name'] for template in templates],
        "template_data": json.dumps([template['template_data'] for template in templates]),
        "template_status": json.dumps([template['status'] for template in templates]),
        "template_button": json.dumps([json.dumps(template['button']) for template in templates]),
        "template_media": json.dumps([template.get('media_type', 'No media available') for template in templates]),
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