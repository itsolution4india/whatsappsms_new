# views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
import requests
import json
import os
from ..utils import get_token_and_app_id, display_whatsapp_id, logger
from ..models import Templates

class TemplateCreateView(LoginRequiredMixin, View):
    login_url = '/'
    
    def get(self, request):
        return render(request, 'create_carousels.html')
    
    def post(self, request):
        TOKEN, _ = get_token_and_app_id(request)
        WABA_ID = display_whatsapp_id(request)
        try:
            data = json.loads(request.body)
            template_name = data['name']
            
            # Prepare template data structure
            template_data = {
                "name": data['name'],
                "language": data['language'],
                "category": data['category'],
                "components": [
                    {
                        "type": "body",
                        "text": data['body_text']
                    },
                    {
                        "type": "carousel",
                        "cards": []
                    }
                ]
            }
            
            # Add cards to template
            for card_data in data['cards']:
                card = {
                    "components": [
                        {
                            "type": "header",
                            "format": "image",
                            "example": {
                                "header_handle": [card_data['media_handle']]
                            }
                        },
                        {
                            "type": "body",
                            "text": card_data['body_text']
                        }
                    ]
                }
                
                # Add buttons if present
                if card_data['buttons']:
                    button_component = {
                        "type": "buttons",
                        "buttons": []
                    }
                    
                    for button in card_data['buttons']:
                        button_data = {
                            "type": button['type'],
                            "text": button['text']
                        }
                        if button['type'] == 'url':
                            button_data['url'] = button['url']
                        button_component['buttons'].append(button_data)
                    
                    card['components'].append(button_component)
                
                template_data['components'][1]['cards'].append(card)
            
            # Make API call to create template
            url = f'https://graph.facebook.com/v21.0/{WABA_ID}/message_templates'
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {TOKEN}'
            }
            
            response = requests.post(url, headers=headers, json=template_data)
            
            if response.status_code == 200:
                try:
                    Templates.objects.create(email=request.user, templates=template_name)
                except Exception as e:
                    logger.error(str(e))
                return JsonResponse({'status': 'success', 'data': response.json()})
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': f"WhatsApp API Error: {response.text}"
                }, status=400)
                
        except Exception as e:
            logger.error(str(e))
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)

class ImageUploadView(LoginRequiredMixin, View):
    login_url = '/'
    
    def post(self, request):
        TOKEN, APP_ID = get_token_and_app_id(request)
        try:
            if 'image' not in request.FILES:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No image file provided'
                }, status=400)

            image = request.FILES['image']
            file_size = image.size
            file_name = image.name

            # Start upload session
            session_url = "https://graph.facebook.com/v21.0/{}/uploads".format(APP_ID)
            
            session_params = {
                "file_name": file_name,
                "file_length": file_size,
                "file_type": "image/jpeg",  
                "access_token": TOKEN
            }
            
            session_response = requests.post(session_url, params=session_params)
            
            if session_response.status_code != 200:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Failed to start upload session: {session_response.text}'
                }, status=400)
            
            session_data = session_response.json()
            upload_session_id = session_data['id']

            # Upload file
            upload_url = f"https://graph.facebook.com/v21.0/{upload_session_id}"
            
            headers = {
                "Authorization": f"OAuth {TOKEN}",
                "file_offset": "0"
            }
            
            file_content = image.read()
            
            upload_response = requests.post(
                upload_url,
                headers=headers,
                data=file_content
            )
            
            if upload_response.status_code != 200:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Failed to upload image: {upload_response.text}'
                }, status=400)
            
            upload_data = upload_response.json()
            
            return JsonResponse({
                'status': 'success',
                'media_handle': upload_data['h']
            })
            
        except Exception as e:
            logger.error(str(e))
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)