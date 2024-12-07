from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from ..models import CustomUser, TemplateLinkage, MessageResponse
from ..utils import logger
from ..functions.template_msg import fetch_templates
from ..functions.flows import get_template_type, get_flow_id
import time
from ..fastapidata import send_api, send_flow_message_api, send_bot_api


@csrf_exempt
def save_phone_number(request):
    if request.method != "POST":
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

    try:
        data = json.loads(request.body)
        response = data.get('response')
        if not response:
            return JsonResponse({'status': 'error', 'message': 'Phone number missing'}, status=400)

        entry = response['entry'][0]['changes'][0]['value']
        phone_number = entry['contacts'][0]['wa_id']
        phone_number_id = entry['metadata']['phone_number_id']
        waba_id = response['entry'][0]['id']
        reply_text = entry.get('messages', [{}])[0].get('button', {}).get('text')
        user_response = entry.get('messages', [{}])[0].get('text', {}).get('body')

        # Fetch emails based on phone_number_id and waba_id
        emails = CustomUser.objects.filter(
            phone_number_id=phone_number_id,
            whatsapp_business_account_id=waba_id
        ).values_list('email', flat=True)

        # Fetch the latest template and linked template names
        latest_template, linked_template_names = get_latest_templates(emails, reply_text)
        
        # Fetch filter message response based on user response
        filter_message_response = get_filter_message_response(emails, user_response)
        
        # Fetch token for the user
        token = get_user_token(phone_number_id)

        # Process templates if found
        if latest_template:
            process_templates(latest_template, waba_id, token, phone_number, phone_number_id)
        # Process message response if found
        elif filter_message_response:
            process_message_response(filter_message_response, token, phone_number_id, phone_number)

        return JsonResponse({'status': 'success'}, status=200)

    except Exception as e:
        logger.error(f"Error processing phone number: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def get_latest_templates(emails, reply_text):
    try:
        latest_template = TemplateLinkage.objects.filter(
            useremail__in=emails,
            button_name=reply_text
        ).order_by('-updated_at')
        linked_template_names = [template.linked_template_name for template in latest_template]
    except Exception as e:
        logger.info(f"{emails} {reply_text}, {str(e)}")
        return None, []
    return latest_template, linked_template_names

def get_filter_message_response(emails, user_response):
    try:
        return MessageResponse.objects.filter(
            user_response=user_response,
            user__in=emails
        ).first()
    except Exception as e:
        return None

def get_user_token(phone_number_id):
    user = CustomUser.objects.filter(phone_number_id=phone_number_id).first()
    return user.register_app.token if user and user.register_app else None

def process_templates(latest_template, waba_id, token, phone_number, phone_number_id):
    for template in latest_template:
        linked_template_name = template.linked_template_name
        campaign_list = fetch_templates(waba_id, token, linked_template_name)
        if not campaign_list:
            continue
        
        template_language = campaign_list[0]['template_language']
        media_type = process_media_type(template.image_id, campaign_list[0]['media_type'])
        
        try:
            if get_template_type(campaign_list, linked_template_name) == "FLOW":
                flow_id = get_flow_id(campaign_list, linked_template_name)
                send_flow_message_api(token, phone_number_id, linked_template_name, flow_id, template_language, [phone_number])
            else:
                send_api(token, phone_number_id, linked_template_name, template_language, media_type, template.image_id, [phone_number], None)
            logger.info(f"Sent template: {linked_template_name} to {phone_number}")
        except Exception as e:
            logger.error(f"Failed to send template: {e}")
        time.sleep(0.5)

def process_media_type(image_id, default_media_type):
    try:
        parts = image_id.split("|")
        if len(parts) >= 2:
            return parts[1]
    except (ValueError, AttributeError):
        pass
    return default_media_type or "TEXT"

def process_message_response(filter_message_response, token, phone_number_id, phone_number):
    message_type = filter_message_response.message_type
    body_message = filter_message_response.body_message

    message_funcs = {
        "list_message": lambda: send_bot_api(token, phone_number_id, phone_number, "list_message", body=body_message, sections=filter_message_response.sections),
        "reply_button_message": lambda: send_bot_api(token, phone_number_id, phone_number, "reply_button_message", body=body_message, button_data=filter_message_response.buttons),
        "single_product_message": lambda: send_bot_api(token, phone_number_id, phone_number, "single_product_message", body=body_message, catalog_id=filter_message_response.catalog_id, product_data={"product_retailer_id": filter_message_response.product_retailer_id}),
        "multi_product_message": lambda: send_bot_api(token, phone_number_id, phone_number, "multi_product_message", body=body_message, catalog_id=filter_message_response.product_section[0].pop("catelogue_id"), sections=filter_message_response.product_section),
        "send_my_location": lambda: send_bot_api(token, phone_number_id, phone_number, "location_message", latitude=filter_message_response.latitude, longitude=filter_message_response.longitude, header=body_message, body=body_message),
        "request_user_location": lambda: send_bot_api(token, phone_number_id, phone_number, "location_request_message", body=body_message),
        "send_text_message": lambda: send_bot_api(token, phone_number_id, phone_number, "text", body=body_message)
    }

    if message_type in message_funcs:
        message_funcs[message_type]()
