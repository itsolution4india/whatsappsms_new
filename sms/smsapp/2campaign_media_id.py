

import requests
import tempfile
import os
# Constants
API_VERSION = "v20.0"
APP_ID1 = "1002275394751227"
APP_ID2 = "465471839698794"
APP_ID3 = "1680208702790856"

# Access tokens
TOKEN1 = "EAAOPkGzfCvsBO5XzFGoAvCFlBdqw436heEJVmk7fsxH6WqXo8wMri5e8SImPpoJivRaITMh7ZAfBnVTmYTAOREpDHQG9jlPANZCrnd5ZBoIZBCZBnzfeqihDjXP2zWl1jwqFxmEsQwZAS7QNxw7bp6YVQj9E1H3KIyVPQhDT1MUyHO42Ifmj7DSOaNtBrYaBJVQeELHhz2UeA4JiDs0hXLSUMt0Lqlvs2a2yRS4ili"
TOKEN2 = "EAAGnWBuof2oBO8EUKs94mmrIeQjrneD9A4lAhZCLQXxZB8HyitAxbyGucbYLm8VoSoxeAsyTsBKioFDSktX3tBe8ytWaWHlS7up2m1BDjy5Y0pZAv4JyPMD4Ujfs7hJZAKE5CIzseNHQyImZAzpNol6AUCuYZAfAUzj1ik4TRXj9OuYfwKVOHPznVb5yZCBOpiP2UWZCYIrIGcUan0TKA9axCc1lrkPl9itO7Van2c7j"
TOKEN3 = "EAAX4JBLg3MgBOZCXmE6QQncXD0ZBeq4FhpZBkODTfVcBxNdMUDkrT0ZC2jzde323MQAkZBB2ikgkZBbJkZBuWajKmDObk5buKyDeOelq76tf6pCDL7EsfsOp5Vaw2T4cBxOsExvqmKtm8P5h6KmC1sd8iY5sY1J1Ojgsjuv8gAZAETsYThuVhvCQHCCJ7SzuH2bzJ50Uv0wVc0AyCLPExmYGFpVXK60zrjtym7znWWIb"

def header_handle(filepath, waba_id):
    ACCESS_TOKEN = None
    APP_ID = None
    upload_url = None
    UPLOAD_SESSION_URL = None
    
    if waba_id in ["332618029945458", "330090043524228", "383548151515080", "391799964022878"]:
        ACCESS_TOKEN = TOKEN1
        APP_ID = APP_ID1
    elif waba_id in ["409990208861505", "397930006742161"]:
        ACCESS_TOKEN = TOKEN3
        APP_ID = APP_ID3
    elif waba_id in ["389460670923677", "401368339722342"]:
        ACCESS_TOKEN = TOKEN2
        APP_ID = APP_ID2
    
    if ACCESS_TOKEN and APP_ID:
        UPLOAD_SESSION_URL = f"https://graph.facebook.com/{API_VERSION}/{APP_ID}/uploads"

        # Get file details
        file_length = filepath.size
        file_extension = filepath.name.split('.')[-1].lower()
        file_type = get_media_format(file_extension)

        params = {
            'file_length': file_length,
            'file_type': file_type,
            'access_token': ACCESS_TOKEN
        }

        response = requests.post(UPLOAD_SESSION_URL, params=params)
        print(response.json())
        response.raise_for_status()

        upload_session_id = response.json().get('id')
        if not upload_session_id:
            raise ValueError("Failed to retrieve upload_session_id from response")

        upload_url = f"https://graph.facebook.com/{API_VERSION}/{upload_session_id}"

        file_offset = 0

        headers = {
            'Authorization': f'Bearer {ACCESS_TOKEN}',
            'file_offset': str(file_offset)
        }

        # Save file to a temporary location
        file_data = handle_uploaded_file(filepath)

        with open(file_data, 'rb') as f:
            file_data1 = f.read()

        response = requests.post(upload_url, headers=headers, data=file_data1)
        print(response.status_code)
    

        return response.json().get('h')

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
    return media_formats.get(file_extension, 'application/octet-stream')


def handle_uploaded_file(file):
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        for chunk in file.chunks():
            tmp_file.write(chunk)
        return tmp_file.name 