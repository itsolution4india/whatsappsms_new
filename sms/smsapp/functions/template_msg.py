import requests
import os
from ..utils import logger

API_VERSION = "v20.0"

def delete_whatsapp_template(waba_id, token, template_name, template_id=None):
    # API endpoint
    base_url = "https://graph.facebook.com/v20.0"
    endpoint = f"{base_url}/{waba_id}/message_templates"

    # Headers
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Parameters
    params = {"name": template_name}
    if template_id:
        params["hsm_id"] = template_id

    # Make the DELETE request
    response = requests.delete(endpoint, headers=headers, params=params)

    # Check the response
    if response.status_code == 200:
        logger.info(f"Template '{template_name}' deleted successfully.")
        return response.json()
    else:
        logger.error(f"Failed to delete template. Status code: {response.status_code} {response.text}")
        return None
    
def header_handle(file_path, ACCESS_TOKEN, APP_ID):
    # ACCESS_TOKEN ,APP_ID=token_data(waba_id)
    file_length = file_path.size
    file_extension = file_path.name.split('.')[-1]
    file_type = get_media_format(file_extension)

    params = {
        'file_length': file_length,
        'file_type': file_type,
        'access_token': ACCESS_TOKEN
    }
    UPLOAD_SESSION_URL = f"https://graph.facebook.com/{API_VERSION}/{APP_ID}/uploads"

    response = requests.post(UPLOAD_SESSION_URL, params=params)
    response.raise_for_status()

    upload_session_id = response.json()['id']
    
    upload_url = f"https://graph.facebook.com/{API_VERSION}/{upload_session_id}"
    file_offset = 0

    headers = {
        'Authorization': f'OAuth {ACCESS_TOKEN}',
        'file_offset': str(file_offset)
    }
    file_data = handle_uploaded_file(file_path)

    with open(file_data, 'rb') as f:
        file_data1 = f.read()

    response = requests.post(upload_url, headers=headers, data=file_data1)
    return response.json()['h']

def get_media_format(file_extension):
    media_formats = {
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
        'gif': 'image/gif', 'bmp': 'image/bmp', 'svg': 'image/svg+xml',
        'mp4': 'video/mp4', 'avi': 'video/x-msvideo', 'mov': 'video/quicktime',
        'flv': 'video/x-flv', 'mkv': 'video/x-matroska', 'mp3': 'audio/mpeg',
        'aac': 'audio/aac', 'ogg': 'audio/ogg', 'wav': 'audio/wav',
        'pdf': 'application/pdf', 'doc': 'application/msword', 'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'ppt': 'application/vnd.ms-powerpoint', 'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'xls': 'application/vnd.ms-excel', 'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'txt': 'text/plain', 'csv': 'text/csv'
    }
    return media_formats.get(file_extension.lower(), 'application/octet-stream')
    
import tempfile

def handle_uploaded_file(file):
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        for chunk in file.chunks():
            tmp_file.write(chunk)
        return tmp_file.name
    
def fetch_templates(waba_id, token, req_template_name=None):
    
    url = f"https://graph.facebook.com/v20.0/{waba_id}/message_templates"
    
    params = {
        'access_token': token,
        "limit": 6000
    }
    
    try:
        # Sending the request to the API
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an error for bad responses

        data = response.json()

        templates = []
        
        # Iterating through the templates in the response
        for entry in data.get("data", []):
            template_id = entry.get("id", "N/A")
            template_language = entry.get("language", "N/A")
            template_name = entry.get("name", "N/A")
            status = entry.get("status", "N/A")
            category = entry.get("category", "N/A")

            body_component = next((comp for comp in entry.get("components", []) if comp.get("type") == "BODY"), None)
            header_component = next((comp for comp in entry.get("components", []) if comp.get("type") == "HEADER"), None)
            button_component = next((comp for comp in entry.get("components", []) if comp.get("type") == "BUTTONS"), None)
            carousel_component = next((comp for comp in entry.get("components", []) if comp.get("type") == "CAROUSEL"), None)
             
            # Extract media link from header component, if available
            media_link = None
            if header_component and 'example' in header_component:
                media_link = header_component['example'].get('header_handle', [None])[0]
                
            image_one, image_two, image_three = None, None, None
            
            if carousel_component:
                images = []
                for card in carousel_component.get('cards', []):
                    header = next((comp for comp in card.get("components", []) if comp.get("type") == "HEADER"), None)
                    if header and 'example' in header:
                        images.extend(header['example'].get('header_handle', []))
                
                # Assign first three images to image_one, image_two, and image_three
                image_one = images[0] if len(images) > 0 else None
                image_two = images[1] if len(images) > 1 else None
                image_three = images[2] if len(images) > 2 else None
                
            num_cards = len(carousel_component['cards']) if carousel_component else 0
            
            # Prepare the template details
            template_data = {
                "template_id": template_id,
                "template_language": template_language,
                "template_name": template_name,
                "media_type": header_component.get("format", "N/A") if header_component else "N/A",
                "media_link": media_link,
                "status": status,
                "category": category,
                "template_data": body_component["text"] if body_component else 'No BODY component found',
                "button": button_component["buttons"] if button_component else None,
                "num_cards": num_cards,
                "image_one": image_one,
                "image_two": image_two,
                "image_three": image_three
            }

            # If req_template_name is provided, filter based on the template name
            if req_template_name:
                if req_template_name.lower() == template_name.lower():
                    templates.append(template_data)
            else:
                templates.append(template_data)
        
        return templates

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching templates: {e}")
        return None