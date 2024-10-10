import requests

def fetch_templates(waba_id, token):
    
    url = f"https://graph.facebook.com/v20.0/{waba_id}/message_templates"
    
    params = {
        'access_token': token
    }
    
    try:

        response = requests.get(url, params=params)
        response.raise_for_status() 
        

        data = response.json()
        
        

        templates = []
        for entry in data.get("data", []):
            template_id = entry.get("id", "N/A")
            template_language = entry.get("language", "N/A")
            media_type=entry.get("format", "N/A")
            template_name = entry.get("name", "N/A")
            status = entry.get("status", "N/A")
            category = entry.get("category", "N/A")
            body_component = next((comp for comp in entry.get("components", []) if comp.get("type") == "BODY"), None)
            header_component = next((comp for comp in entry.get("components", []) if comp.get("type") == "HEADER"), None)
            button_component = next((comp for comp in entry.get("components", []) if comp.get("type") == "BUTTONS"), None)
             
            media_link = None
            if header_component and 'example' in header_component:
                media_link = header_component['example'].get('header_handle', [None])[0]
            
            templates.append({
                "template_id": template_id,
                "template_language":template_language,
                "template_name": template_name,
                "media_type":header_component.get("format", "N/A") if header_component else "N/A",
                "media_link":media_link,
                "status": status,
                "category": category,
                "template_data": body_component["text"] if body_component else 'No BODY component found',
                "button":button_component["buttons"] if button_component else None
            })
        
        return templates
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching templates: {e}")
        return None

'''
if __name__ == "__main__":
    waba_id = "330090043524228"
    fetched_templates = fetch_templates(waba_id)
    if fetched_templates:
        print("Fetched templates:")
        for template in fetched_templates:
            print(template)
    else:
        print("Failed to fetch templates.")
'''