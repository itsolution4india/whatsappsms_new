import typing as ty
import logging
import requests

def send_interactive_message(
    token: str,
    phone_number_id: str,
    contact: str,
    message_type: str,
    header: ty.Optional[str] = None,
    body: ty.Optional[str] = None,
    footer: ty.Optional[str] = None,
    button_data: ty.Optional[ty.List[ty.Dict[str, str]]] = None,
    product_data: ty.Optional[ty.Dict] = None,
    catalog_id: ty.Optional[str] = None,
    sections: ty.Optional[ty.List[ty.Dict]] = None,
    latitude: ty.Optional[float] = None,
    longitude: ty.Optional[float] = None,
    media_id: ty.Optional[str] = None
) -> None:
    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": contact,
        "type": "interactive"
    }

    if message_type == "text":
        payload["type"] = "text"
        payload["text"] = {
            "preview_url": False,
            "body": body
        }

    elif message_type == "image":
        payload["type"] = "image"
        payload["image"] = {
            "id": media_id,
            "caption": body if body else None
        }

    elif message_type == "document":
        payload["type"] = "document"
        payload["document"] = {
            "id": media_id,
            "caption": body if body else None,
            "filename": header if header else "document"
        }

    elif message_type == "video":
        payload["type"] = "video"
        payload["video"] = {
            "id": media_id,
            "caption": body if body else None
        }

    elif message_type == "video":
        payload["interactive"] = {
            "type": "text",
            "header": {
                "type": "video",
                "video": {
                    "id": media_id
                }
            },
            "body": {"text": body} if body else None
        }

    elif message_type == "list_message":
        payload["interactive"] = {
            "type": "list",
            "header": {"type": "text", "text": header} if header else None,
            "body": {"text": body},
            "footer": {"text": footer} if footer else None,
            "action": {
                "button": "Choose an option",
                "sections": sections
            }
        }
    
    elif message_type == "reply_button_message":
        payload["interactive"] = {
            "type": "button",
            "body": {"text": body},
            "footer": {"text": footer} if footer else None,
            "action": {
                "buttons": button_data
            }
        }

    elif message_type == "single_product_message":
        payload["interactive"] = {
            "type": "product",
            "body": {"text": body},
            "footer": {"text": footer} if footer else None,
            "action": {
                "catalog_id": catalog_id,
                "product_retailer_id": product_data["product_retailer_id"]
            }
        }
    
    elif message_type == "multi_product_message":
        payload["interactive"] = {
            "type": "product_list",
            "header": {"type": "text", "text": header} if header else None,
            "body": {"text": body},
            "footer": {"text": footer} if footer else None,
            "action": {
                "catalog_id": catalog_id,
                "sections": sections
            }
        }
    
    elif message_type == "location_message":
        payload["type"] = "location"
        payload["location"] = {
            "latitude": latitude,
            "longitude": longitude,
            "name": header,
            "address": body
        }
    
    elif message_type == "location_request_message":
        payload["interactive"] = {
            "type": "LOCATION_REQUEST_MESSAGE",
            "body": {
                "text": body
            },
            "action": {
                "name": "send_location"
            }
        }

    logging.info(f"Sending {message_type} to {contact} via {phone_number_id}")

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            print(f"Failed to send {message_type} to {contact}. Status: {response.status_code}")
            print(response.json())
            return
    except Exception as e:
        logging.error(f"Error sending {message_type} to {contact}: {e}")
        return