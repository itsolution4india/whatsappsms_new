import requests
import json
from dotenv import load_dotenv
import os

load_dotenv()

base_url = os.getenv("FASTAPI_BASE_URL")

def send_api(phone_number_id, template_name, language, media_type, media_id, contact):
    url = f"{base_url}/"
    headers = {
    'Content-Type': 'application/json'
    }

# Define the data payload
    data = {
    "phone_number_id":phone_number_id,
    "template_name": template_name,
    "language": language,
    "media_type": media_type,
    "media_id": media_id,
    "contact_list": contact
    }

    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    
    return 


