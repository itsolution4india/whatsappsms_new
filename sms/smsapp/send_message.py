import typing as ty
import requests
import json
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Function to send a single message
def send_message(phone_number_id: str, template_name: str, language: str, media_type: str, media_id: ty.Optional[str], contact: str) -> bool:
    url = f'https://graph.facebook.com/v20.0/{phone_number_id}/messages'
    access_token = "EAAE3ZCQ8LZB48BO9KDbpZCjbM6ZADGoAZANvtahzlAaoRqF24zgwUYsGZCSVpi1IkOhgaGnfCzmh5axAWDrXyomeqmhYUSgofSlIXojlBBCkwguOsFUgeCIaXuUZAsBhMiSTBFwyqZCkFTwGV1n700ef4fe1iZAGqVuBr2x9ZAh8AUz3FxxXIOWfDf6xinJAreZChYwFwZDZD"
    if not access_token:
        logger.error("Access token is not set.")
        return False

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    header_component = {"type": "header", "parameters": []}
    
    if media_id and media_type in ["IMAGE", "DOCUMENT", "VIDEO", "AUDIO"]:
        header_component["parameters"].append({
            "type": media_type.lower(),
            media_type.lower(): {"id": media_id}
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": contact,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            "components": [header_component, {"type": "body", "parameters": []}]
        }
    }

    
    #requests.post(url, headers=headers, data=json.dumps(payload))
    return True
      
# Function to send messages in batches
def send_messages(phone_number_id: str, template_name: str, language: str, media_type: str, media_id: ty.Optional[str], contact_list: ty.List[str]):
    for batch in chunks(contact_list, 1000):  # Send messages in batches of 50
        for contact in batch:
            send_message(phone_number_id, template_name, language, media_type, media_id, contact)

def chunks(lst: ty.List[str], size: int) -> ty.Generator[ty.List[str], None, None]:
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

# Main function to send messages via API
def send_messages_api(phone_number_id: str, template_name: str, language: str, media_type: str, media_id: ty.Optional[str], contact_list: ty.List[str]) -> dict:
    try:
        send_messages(phone_number_id, template_name, language, media_type, media_id, contact_list)
    except Exception as e:
        #logger.error(f"Error processing request: {e}")
        return {'message': 'Error processing the request'}

    return {'message': 'Messages sent successfully'}


