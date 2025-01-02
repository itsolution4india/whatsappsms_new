import requests
from typing import List, Dict, Optional
from requests.exceptions import RequestException
from django.shortcuts import get_object_or_404
import json
from decimal import Decimal
from .utils import insert_bot_sent_message, logger, generate_code
from .models import ReportInfo, Notifications

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def send_api(token: str, phone_number_id: str, template_name: str, language: str, media_type: str, media_id: Optional[str], contact_list: List[str], variable_list: List[str], response_req=None, email=None):
    request_id = generate_code()
    request_id = f"MESSAGE{request_id}"
    url="https://wtsdealnow.in/send_sms/"
    
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    data = {
        "token":token,
        "phone_number_id": phone_number_id,
        "template_name": template_name,
        "language": language,
        "media_type": media_type,
        "media_id": media_id if media_id else "",
        "contact_list": contact_list,
        "variable_list": variable_list if variable_list else None,
        'request_id': request_id
    }
    
    response = requests.post(url, headers=headers, json=data)
    logger.info(response.json())
    if response.status_code == 200:
        response_data = response.json()
        unique_id = response_data.get("unique_id")
        
        if request_id and unique_id:
            try:
                if email and template_name and request_id and unique_id:
                    Notifications.objects.create(
                        email=email,
                        campaign_title=template_name,
                        start_request_id=unique_id,
                        request_id=request_id,
                        text = "message"
                    )
                    logger.info(f"Added notification entry for {email} with request ID {request_id} and unique ID {unique_id}")
            except Exception as e:
                logger.error(f"Failed to update report {request_id}: {e}")
        else:
            logger.error(f"Missing unique_id or report_id in response: {response_data}")
    else:
        logger.error(f"Failed to send validation request: {response.status_code} - {response.text}")
    if response_req:
        return response
    return 
# Example usage

def send_validate_req(token: str, phone_number_id: str, contact_list: List[str], body_text: str, report_id=None):
    url = "https://wtsdealnow.in/validate_numbers_api/"
    
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    data = {
        "token": token,
        "phone_number_id": phone_number_id,
        "contact_list": contact_list,
        "body_text": body_text,
        "report_id": str(report_id) if report_id else None
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Raw response text: {response.text}")

        # Check if the response content is empty or not valid JSON
        if response.status_code == 200:
            try:
                response_data = response.json()
                logger.info(f"Parsed JSON response: {response_data}")
            except ValueError as e:
                logger.error(f"Failed to parse JSON: {str(e)}")
                return response
            
            unique_id = response_data.get("unique_id")
            
            if report_id and unique_id:
                try:
                    report_instance = get_object_or_404(ReportInfo, id=report_id)
                    report_instance.start_request_id = unique_id
                    report_instance.save()
                    logger.info(f"Updated report {report_id} with unique_id {unique_id}")
                except Exception as e:
                    logger.error(f"Failed to update report {report_id}: {e}")
            else:
                logger.error(f"Missing unique_id or report_id in response: {response_data}")
        else:
            logger.error(f"Failed to send validation request: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")

    return response

def send_flow_message_api(token: str, phone_number_id: str, template_name: str, flow_id: str, language: str, recipient_phone_number: List[str], email=None):
    request_id = generate_code()
    request_id = f"FLOW{request_id}"
    url = "https://wtsdealnow.in/send_flow_message/"
    
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    data = {
        "token": token,
        "phone_number_id": phone_number_id,
        "template_name": template_name,
        "flow_id": str(flow_id),
        "language": language,
        "recipient_phone_number": recipient_phone_number,
        'request_id': request_id
    }
    
    response = requests.post(url, headers=headers, json=data)
    logger.info(response.json())
    if response.status_code == 200:
        response_data = response.json()
        unique_id = response_data.get("unique_id")
        
        if request_id and unique_id:
            try:
                if email and template_name and request_id and unique_id:
                    Notifications.objects.create(
                        email=email,
                        campaign_title=template_name,
                        start_request_id=unique_id,
                        request_id=request_id,
                        text = "flows"
                    )
                    logger.info(f"Added notification entry for {email} with request ID {request_id} and unique ID {unique_id}")
            except Exception as e:
                logger.error(f"Failed to update report {request_id}: {e}")
        else:
            logger.error(f"Missing unique_id or report_id in response: {response_data}")
    else:
        logger.error(f"Failed to send validation request: {response.status_code} - {response.text}")
        
    return response.status_code, response.json()
    
def send_carousel_message_api(token: str, phone_number_id: str, template_name: str, recipient_phone_number: List[str], media_id_list: List[str], template_details: dict):
    url = "https://wtsdealnow.in/send_carousel_messages/"
    
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    data = {
        "token": token,
        "phone_number_id": phone_number_id,
        "template_name": template_name,
        "contact_list": recipient_phone_number,
        "media_id_list": media_id_list,
        "template_details": template_details
    }
    
    response = requests.post(url, headers=headers, json=data)
    return response

def send_bot_api(
    token: str,
    phone_number_id: str,
    contact_list: List[str],
    message_type: str,
    header: Optional[str] = None,
    body: Optional[str] = None,
    footer: Optional[str] = None,
    button_data: Optional[List[Dict[str, str]]] = None,
    product_data: Optional[Dict] = None,
    catalog_id: Optional[str] = None,
    sections: Optional[List[Dict]] = None,
    latitude: Optional[float | Decimal] = None,
    longitude: Optional[float | Decimal] = None,
    media_id: Optional[str] = None
) -> Dict:
    url = "https://wtsdealnow.in/bot_api/"
    
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    contacts = [contact_list] if isinstance(contact_list, str) else contact_list
    
    # Convert Decimal values to float if present
    lat = float(latitude) if isinstance(latitude, Decimal) else latitude
    lon = float(longitude) if isinstance(longitude, Decimal) else longitude
    
    data = {
        "token": token,
        "phone_number_id": phone_number_id,
        "contact_list": contacts,
        "message_type": message_type,
        "header": header,
        "body": body,
        "footer": footer,
        "button_data": button_data,
        "product_data": product_data,
        "catalog_id": catalog_id,
        "sections": sections,
        "latitude": lat,
        "longitude": lon,
        "media_id": media_id,
    }
    
    # Remove None values from the data
    t = {k: v for k, v in data.items() if v is not None}
    logger.info(f"fastapi {url} {headers} {t}")
    logger.info(f"{type(contacts)}")
    
    try:
        insert_bot_sent_message(token=token,phone_number_id=phone_number_id,contacts=contacts,message_type=message_type,header=header,body=body,footer=footer,button_data=button_data,product_data=product_data,catalog_id=catalog_id,sections=sections,lat=lat,lon=lon,media_id=media_id)
        logger.info("BotSentMessages successfully saved in the database")
        
    except Exception as e:
        logger.error(f"Error saving BotSentMessages: {e}")

    try:
        # Convert the data to JSON string using the custom encoder
        json_data = json.dumps(t, cls=DecimalEncoder)
        
        # Send the request with the JSON string
        response = requests.post(url, headers=headers, data=json_data)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        return response.json()
    
    except requests.exceptions.ConnectionError as conn_err:
        raise RequestException(f"Error connecting to server: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        raise RequestException(f"Timeout error: {timeout_err}")
    except requests.exceptions.RequestException as err:
        raise RequestException(f"An error occurred: {err}")
    except ValueError as val_err:
        raise ValueError(f"Invalid data format: {val_err}")
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}, Response: {response.text}")
        raise RequestException(f"HTTP error occurred: {http_err}")
    except Exception as e:
        logger.error(f"Error: {e}")
        raise