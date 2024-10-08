import requests

def template_create(token, waba_id, template_name, language, category, header_type, header_content, body_text, footer_text, call_button_text, phone_number, url_button_text, website_url, quick_reply_one, quick_reply_two, quick_reply_three):
    
    url = f'https://graph.facebook.com/v20.0/{waba_id}/message_templates'
    components = []
    token = f'Bearer {token}'
    # Create header component if provided
    if header_type and header_content:
        if header_type == "headerText":
            components.append({
                "type": "HEADER",
                "format": "TEXT",
                "text": header_content
            })
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

    
    
'''
template_create(
    waba_id="318794741325676",
    template_name="example_template1",
    language="en_US",
    category="Marketing",
    header_type="headerImage",
    header_content="4::YXBwbGljYXRpb24vb2N0ZXQtc3RyZWFt:ARbp3NxfKCTnotO_6ZojyIsDak1YDrcmaku_jJl4cJvKk-nrt6lKBgNDKTf-G9kElPUR-74ab9bwgGOqSunXE_6HkQz1ltZL3_23pnKYcg0Zxg:e:1720928506:1002275394751227:61560603673003:ARbQbHWnFfKRtUWd7_g",
    body_text="This is the body of the template.",
    footer_text="This is the footer.",
    call_button_text="Call Us",
    phone_number="+917905968734",
    url_button_text="Visit Website",
    website_url="https://example.com"
)

'''