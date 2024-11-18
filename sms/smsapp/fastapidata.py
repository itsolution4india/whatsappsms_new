import requests
import logging
from typing import List, Dict, Optional
from requests.exceptions import RequestException
import json
from decimal import Decimal

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def send_api(token: str, phone_number_id: str, template_name: str, language: str, media_type: str, media_id: Optional[str], contact_list: List[str], variable_list: List[str]):
    #url = 'http://127.0.0.1:8000/send_sms/'
    url="https://sendsms-fastapi.onrender.com/send_sms/"
    
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
        "variable_list": variable_list if variable_list else None
    }
    
    response = requests.post(url, headers=headers, json=data)
    #print(data)
    #print("Status Code:", response.status_code)
    #print("Response JSON:", response.json())
    return 
# Example usage

def send_flow_message_api(token: str, phone_number_id: str, template_name: str, flow_id: str, language: str, recipient_phone_number: List[str]):
    url = "https://sendsms-fastapi.onrender.com/send_flow_message/"
    
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
        "recipient_phone_number": recipient_phone_number
    }
    
    response = requests.post(url, headers=headers, json=data)
    return response.status_code, response.json()
    

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
    url = "https://sendsms-fastapi.onrender.com/bot_api/"
    
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
    logging.info(f"fastapi {url} {headers} {t}")
    logging.info(f"{type(contacts)}")
    
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
        logging.error(f"Error: {e}")
        raise