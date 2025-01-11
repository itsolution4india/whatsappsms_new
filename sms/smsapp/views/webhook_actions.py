from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from ..models import CustomUser, TemplateLinkage, MessageResponse
from ..utils import logger
from ..functions.template_msg import fetch_templates
from ..functions.flows import get_template_type, get_flow_id
import time
from ..utils import insert_bot_sent_message
from ..fastapidata import send_api, send_flow_message_api, send_bot_api
from django.db.models import Q


@csrf_exempt
def save_phone_number(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            response = data.get('response')
            if response:
                phone_number = response['entry'][0]['changes'][0]['value']['contacts'][0]['wa_id']
                try:
                    reply_text = response['entry'][0]['changes'][0]['value']['messages'][0]['button']['text']
                except (KeyError, IndexError):
                    reply_text = None
                    pass
                try:
                    user_response = response['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
                except (KeyError, IndexError):
                    pass
                phone_number_id = response['entry'][0]['changes'][0]['value']['metadata']['phone_number_id']
                waba_id = response['entry'][0]['id']
                emails = CustomUser.objects.filter(
                    phone_number_id=phone_number_id,
                    whatsapp_business_account_id=waba_id
                ).values_list('email', flat=True)

                try:
                    latest_template = TemplateLinkage.objects.filter(
                        useremail__in=emails,
                        button_name=reply_text
                    ).order_by('-updated_at')
                    linked_template_names = [template.linked_template_name for template in latest_template]
                except Exception as e:
                    logger.info(f"{emails}, {str(e)}")
                    linked_template_names = []
                    latest_template = None

                try:
                    filter_message_response = MessageResponse.objects.filter(
                        Q(user_response__iexact=user_response) &
                        Q(user__in=emails)
                    ).first()
                    logger.info("bot automation message")
                except Exception as e:
                    filter_message_response = None
                
                if reply_text and not latest_template:
                    try:
                        filter_message_response = MessageResponse.objects.filter(
                            Q(user_response__iexact=reply_text) &
                            Q(user__in=emails)
                        ).first()
                        logger.info("bot automation message")
                    except Exception as e:
                        filter_message_response = None
                logger.info(f"reply_text: {reply_text}, {user_response}")
                latest_user = CustomUser.objects.filter(
                        phone_number_id=phone_number_id
                    ).first()
                if latest_user and latest_user.register_app:
                    token = latest_user.register_app.token

                if latest_template:
                    logger.info("detected linktemplate message")
                    for template in latest_template:
                        linked_template_name = template.linked_template_name
                        campaign_list = fetch_templates(waba_id, token, linked_template_name)
                        filter_campaign_list = [
                            {'template_language': item['template_language'], 'media_type': item['media_type']}
                            for item in campaign_list
                        ]
                        lang = filter_campaign_list[0]['template_language']
                        temp_media_type = filter_campaign_list[0]['media_type']
                        image_id = template.image_id
                        
                        try:
                            parts = image_id.split("|")
                            if len(parts) >= 2:
                                image_id = parts[0]
                                media_type = parts[1]
                            else:
                                raise ValueError("image_id format is incorrect. Expected format: 'id|type'")
                        
                        except Exception as e:
                            logger.error(f"Error {e}")
                            image_id = None
                            media_type = "TEXT"
                        
                        if media_type in ["image/jpeg", "image/png"]:
                            media_type = "IMAGE"
                        try:
                            campaign_list = fetch_templates(waba_id, token)
                            if campaign_list is None :
                                campaign_list=[]
                            template_type = get_template_type(campaign_list, linked_template_name)
                            if template_type == "FLOW":
                                flow_id = get_flow_id(campaign_list, linked_template_name)
                                status_code, _ = send_flow_message_api(token, phone_number_id, linked_template_name, flow_id, lang, [phone_number])
                            else:
                                send_api(str(token), str(phone_number_id), str(linked_template_name), lang, str(media_type), str(image_id), [phone_number], None)
                            logger.info(f"Next reply message sent successfully. Template: {linked_template_name}, Phone Number: {phone_number}, Media Type: {type(str(media_type))} {str(media_type)}, Image ID Type: {type(str(image_id))} {str(image_id)}")
                        except Exception as e:
                            logger.error(f"Failed to send next reply message {e}")
                        
                        time.sleep(0.5)
                            
                elif filter_message_response:
                    logger.info("detected bot message")
                    message_type = filter_message_response.message_type
                    if message_type == "list_message":
                        response = send_bot_api(token, phone_number_id, phone_number, "list_message", body=filter_message_response.body_message, sections=filter_message_response.sections)
                    elif message_type == "reply_button_message":
                        response = send_bot_api(token, phone_number_id, phone_number, "reply_button_message", body=filter_message_response.body_message, button_data=filter_message_response.buttons)
                    elif message_type == "single_product_message":
                        product_data = {"product_retailer_id": filter_message_response.product_retailer_id}
                        response = send_bot_api(token, phone_number_id, phone_number, "single_product_message", body=filter_message_response.body_message, catalog_id=filter_message_response.catalog_id, product_data=product_data)
                    elif message_type == "multi_product_message":
                        multi_product_section = filter_message_response.product_section
                        catelogue_id = multi_product_section[0].pop("catelogue_id")
                        response = send_bot_api(token, phone_number_id, phone_number, "multi_product_message", body=filter_message_response.body_message, catalog_id=catelogue_id, sections=multi_product_section)
                    elif message_type == "send_my_location":
                        response = send_bot_api(token, phone_number_id, phone_number, "location_message", latitude=filter_message_response.latitude, longitude=filter_message_response.longitude, header=filter_message_response.body_message, body=filter_message_response.body_message)
                    elif message_type == "request_user_location":
                        response = send_bot_api(token, phone_number_id, phone_number, "location_request_message", body=filter_message_response.body_message)
                    elif message_type == "send_text_message":
                        response = send_bot_api(token, phone_number_id, phone_number, "text", body=filter_message_response.body_message)
                    elif message_type == 'link_template':
                        try:
                            insert_bot_sent_message(token=token,phone_number_id=phone_number_id,contacts=phone_number,message_type=message_type,header=None,body=None,footer=None,button_data=None,product_data=product_data,catalog_id=None,sections=None,lat=None,lon=None,media_id=None)
                            logger.info("BotSentMessages successfully saved in the database")
                            
                        except Exception as e:
                            logger.error(f"Error saving BotSentMessages: {e}")
                        image_id = filter_message_response.catalog_id
                        campaign_list = fetch_templates(waba_id, token, filter_message_response.template_name)
                        filter_campaign_list = [
                            {'template_language': item['template_language'], 'media_type': item['media_type']}
                            for item in campaign_list
                        ]
                        lang = filter_campaign_list[0]['template_language']
                        temp_media_type = filter_campaign_list[0]['media_type']
                        if image_id and image_id != 'nan' and image_id != None:
                            logger.info(f"sent bot message, {filter_message_response.template_name} {lang}, {temp_media_type} {str(image_id)}")
                            send_api(token, phone_number_id, filter_message_response.template_name, lang, temp_media_type, str(image_id), [phone_number], None)
                        else:
                            logger.info(f"sent bot message, {filter_message_response.template_name} {lang}, {temp_media_type}")
                            send_api(token, phone_number_id, filter_message_response.template_name, lang, temp_media_type, None, [phone_number], None)
                    
                # You can also save it in your model if needed
                return JsonResponse({'status': 'success'}, status=200)
            else:
                return JsonResponse({'status': 'error', 'message': 'Phone number missing'}, status=400)
        except Exception as e:
            logger.error(f"Error processing phone number: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
