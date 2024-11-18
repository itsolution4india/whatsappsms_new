import requests

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
        print(f"Template '{template_name}' deleted successfully.")
        return response.json()
    else:
        print(f"Failed to delete template. Status code: {response.status_code}")
        print(f"Response: {response.text}")
        return None