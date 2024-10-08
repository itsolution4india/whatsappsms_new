import requests
from typing import Optional, List

def send_api(token: str, phone_number_id: str, template_name: str, language: str, media_type: str, media_id: Optional[str], contact_list: List[str]):
    #url = 'http://127.0.0.1:8000/send_sms/'
    url="https://dataapi-chi.vercel.app/send_sms/"
    
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
        "contact_list": contact_list
    }
    
    response = requests.post(url, headers=headers, json=data)
    #print(data)
    #print("Status Code:", response.status_code)
    #print("Response JSON:", response.json())
    return 
# Example usage
'''
send_messages_api(
    phone_number_id="281807641692911",
    template_name="itsolutiontemp",
    language="en_US",
    media_type="TEXT",
    media_id="",
    contact_list=["7905968734"]
)
'''

