import requests
import json
import time
import logging
from django.utils import timezone
from django.contrib import messages
from ..models import ReportInfo
from ..display_templates import fetch_templates
from ..fastapidata import send_flow_message_api
from .send_messages import schedule_subtract_coins, subtract_coins



def get_flow_id(data, template_name):
    if isinstance(data, list):
        templates = data
    elif isinstance(data, dict):
        templates = data.get('data', [])
    else:
        return None

    for template in templates:
        if template.get('template_name') == template_name:
            components = template.get('button', [])  # Corrected to 'button' field
            for component in components:
                if component.get('type') == 'FLOW':
                    return str(component.get('flow_id'))
    return None
    
def get_template_type(data, template_name):
    for template in data:
        if template.get('template_name') == template_name:
            buttons = template.get('button', [])
            if buttons:
                return buttons[0].get('type')
    return None

def create_template_with_flow(flow_json, WABA_ID, ACCESS_TOKEN, body_text, flow_name, category, language, first_screen_id):
    BASE_URL = 'https://graph.facebook.com/v20.0'
    url = f"{BASE_URL}/{WABA_ID}/message_templates"
    
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    data = {
        "name": flow_name,
        "language": language,
        "category": category,
        "components": [
            {
                "type": "body",
                "text": body_text
            },
            {
                "type": "BUTTONS",
                "buttons": [
                    {
                        "type": "FLOW",
                        "text": "Start Survey",
                        "navigate_screen": first_screen_id,
                        "flow_action": "navigate",
                        "flow_json": json.dumps(flow_json)
                    }
                ]
            }
        ]
    }
    
    response = requests.post(url, headers=headers, json=data)
    response_dict = response.json()
    
    return response.status_code,response_dict

def send_flow_messages_with_report(current_user, token, phone_id, campaign_list, flow_name, all_contact, contact_list, campaign_title, request):
    try:
        logging.info(f"Sending flow messages for user: {current_user}, flow_name: {campaign_title}")
        for campaign in campaign_list:
            if campaign['template_name'] == flow_name:
                language = campaign['template_language']
                money_data = len(all_contact)
                logging.info(f"Calculated money data for sending flow messages: {money_data}")

                if request:
                    subtract_coins(request, money_data)
                else:
                    schedule_subtract_coins(current_user, money_data)
                
                try:
                    flow_id = get_flow_id(campaign_list, flow_name)
                except Exception as e:
                    logging.error(f"Failed to get flow_id: {e}")
                    return
                _, _ = send_flow_message_api(token, phone_id, flow_name, flow_id, language, contact_list)

        formatted_numbers = []
        for number in all_contact:
            if number.startswith("+91"):
                formatted_numbers.append("91" + number[3:])
            elif not number.startswith("91"):
                formatted_numbers.append("91" + number)
            else:
                formatted_numbers.append(number)

        phone_numbers_string = ",".join(formatted_numbers)

        ReportInfo.objects.create(
            email=str(current_user),
            campaign_title=campaign_title,
            contact_list=phone_numbers_string,
            message_date=timezone.now(),
            message_delivery=len(all_contact),
            template_name=flow_name
        )
        logging.info(f"Messages sent successfully for campaign: {campaign_title}, user: {current_user}")
    except Exception as e:
        logging.error(f"Error in sending messages: {str(e)}")
        
def get_flows(ACCESS_TOKEN, WABA_ID):
    BASE_URL = 'https://graph.facebook.com/v20.0'
    
    url = f"{BASE_URL}/{WABA_ID}/flows"
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}'
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            flows = response.json().get('data', [])
            return flows
        else:
            error_message = f"Failed to retrieve flows. Status code: {response.status_code}"
            return error_message
    except Exception as e:
        return str(e)
        

def create_message_template_with_flow(waba_id, body_text, lang, category, access_token, template_name, flow_id):
    print(waba_id, body_text, lang, category, access_token, template_name, flow_id)
    base_url = 'https://graph.facebook.com/v20.0'
    url = f"{base_url}/{waba_id}/message_templates"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "name": template_name,
        "language": lang,
        "category": category,
        "components": [
            {
                "type": "body",
                "text": body_text
            },
            {
                "type": "BUTTONS",
                "buttons": [
                    {
                        "type": "FLOW",
                        "text": "Open flow!",
                        "navigate_screen": "ITSOLUTION",
                        "flow_action": "navigate",
                        "flow_id": int(flow_id)
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        print(response.json())
        print("Response Content:", response.text)
        print("Response Status Code:", response.status_code)
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(str(e))
        return response