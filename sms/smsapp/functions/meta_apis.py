import requests
import json
from ..utils import logger
import typing as ty

def send_message(token: str, phone_number_id: str, template_name: str, language: str, media_type: str, media_id: ty.Optional[str], contact: str, variables: ty.Optional[ty.List[str]] = None, csv_variable_list: ty.Optional[ty.List[str]] = None) -> dict:
    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    header_component = {
        "type": "header",
        "parameters": []
    }

    body_component = {
        "type": "body",
        "parameters": []
    }
    
    # Use CSV variable list if provided
    if csv_variable_list:
        variables = csv_variable_list[1:]
        contact = str(csv_variable_list[0])
    
    # Populate body parameters if variables exist
    if variables:
        body_component["parameters"] = [
            {
                "type": "text",
                "text": variable
            } for variable in variables
        ]

    # Prepare context information
    context_info = json.dumps({
        "template_name": template_name,
        "language": language,
        "media_type": media_type
    })

    # Add media parameter if media ID and type are provided
    if media_id and media_type in ["IMAGE", "DOCUMENT", "VIDEO", "AUDIO"]:
        header_component["parameters"].append({
            "type": media_type.lower(),
            media_type.lower(): {"id": media_id}
        })

    # Build payload for sending the message
    payload = {
        "messaging_product": "whatsapp",
        "to": contact,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            "components": [
                header_component,
                body_component
            ]
        },
        "context": {
            "message_id": f"template_{template_name}_{context_info}"
        }
    }

    try:
        # Send POST request
        response = requests.post(url, json=payload, headers=headers)
        response_text = response.text
        
        # Handle successful response
        if response.status_code == 200:
            return {
                "status": "success",
                "contact": contact,
                "message_id": f"template_{template_name}_{context_info}",
                "response": response_text
            }
        else:
            # Log and return error for non-200 status codes
            logger.error(f"Failed to send message to {contact}. Status: {response.status_code}, Error: {response_text}")
            return {
                "status": "failed",
                "contact": contact,
                "error_code": response.status_code,
                "error_message": response_text
            }
    except requests.RequestException as e:
        # Handle request exceptions
        logger.error(f"Error sending message to {contact}: {e}")
        return {
            "status": "failed",
            "contact": contact,
            "error_code": "client_error",
            "error_message": str(e)
        }