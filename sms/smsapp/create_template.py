import requests
import json
from typing import List, Dict

def template_create(token, waba_id, template_name, language, category, header_type, header_content, body_text, footer_text, call_button_text, phone_number, url_button_text, website_url, quick_reply_one, quick_reply_two, quick_reply_three, body_example_values=None):
    
    url = f'https://graph.facebook.com/v20.0/{waba_id}/message_templates'
    components = []
    token = f'Bearer {token}'
    # Create header component if provided
    if header_type and header_content:
        if header_type == "headerText":
            header_comp = {
                "type": "HEADER",
                "format": "TEXT",
                "text": header_content
            }
            # Add example if header contains variables
            if "{{" in header_content:
                header_comp["example"] = {
                    "header_text": [header_content.replace("{{1}}", "John")]
                }
            components.append(header_comp)

        elif header_type in ["headerImage", "headerDocument", "headerVideo","headerAudio"]:
            components.append({
                "type": "HEADER",
                "format": header_type.split("header")[-1].upper(),
                "example": {
                    "header_handle": [
                        header_content
                    ]
                }
            })
        else:
            
            return

    # Add body component
    if body_example_values:
        body_comp = {
            "type": "BODY",
            "text": body_text,
            "example": {
                "body_text": [
                    ["Sample"]  # Default example
                ]
            }
        }

        if body_example_values:
            body_comp["example"]["body_text"] = [body_example_values]
        
        components.append(body_comp)
    else:
        components.append({
            "type": "BODY",
            "text": body_text
        })

    # Add footer component if provided
    if footer_text:
        components.append({
            "type": "FOOTER",
            "text": footer_text
        })

    # Create button components if provided
    buttons = []
    if call_button_text and phone_number:
        buttons.append({
            "type": "PHONE_NUMBER",
            "text": call_button_text,
            "phone_number":phone_number
        })
    if quick_reply_one:
        buttons.append({
            "type": "QUICK_REPLY",
            "text": quick_reply_one
        })
    if quick_reply_two:
        buttons.append({
            "type": "QUICK_REPLY",
            "text": quick_reply_two
        })
    if quick_reply_three:
        buttons.append({
            "type": "QUICK_REPLY",
            "text": quick_reply_three
        })
    if url_button_text and website_url:
        buttons.append({
            "type": "URL",
            "text": url_button_text,
            "url": website_url
        })
    if buttons:
        components.append({
            "type": "BUTTONS",
            "buttons": buttons
        })

    payload = {
        "name": template_name,
        "language": language,
        "category": category,
        "components": components
    }

    headers = {
        'Authorization': token
    }
    
    response = requests.post(url=url, json=payload, headers=headers)
    response_dict = response.json()
    
   
   
    return response.status_code,response_dict

def create_auth_template(
    waba_id: str,
    access_token: str,
    template_name: str,
    languages: List[str],
    add_security_recommendation: bool = True,
    code_expiration_minutes: int = 10,
    otp_type: str = "COPY_CODE",
    app_configs: List[Dict[str, str]] = None
) -> Dict:

    url = f"https://graph.facebook.com/v17.0/{waba_id}/upsert_message_templates"
    
    button = {
        "type": "OTP",
        "otp_type": otp_type
    }
    
    if otp_type in ["ONE_TAP", "ZERO_TAP"] and app_configs:
        button["supported_apps"] = app_configs
    
    payload = {
        "name": template_name,
        "languages": languages,
        "category": "AUTHENTICATION",
        "components": [
            {
                "type": "BODY",
                "add_security_recommendation": add_security_recommendation
            },
            {
                "type": "FOOTER",
                "code_expiration_minutes": code_expiration_minutes
            },
            {
                "type": "BUTTONS",
                "buttons": [button]
            }
        ]
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    
    try:
        response = requests.post(
            url,
            headers=headers,
            data=json.dumps(payload)
        )
        
        response.raise_for_status()
        
        return response.status_code, response.json()
    
    except requests.exceptions.RequestException as e:
        print(f"Error creating template: {str(e)}")
        if hasattr(e.response, 'text'):
            print(f"Response content: {e.response.text}")
        raise