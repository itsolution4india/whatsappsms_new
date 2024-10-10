import requests
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

def generate_id(phone_number_id, media_type, uploaded_file, access_token):
    url = f'https://graph.facebook.com/v20.0/{phone_number_id}/media'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    data = {
        'type': media_type,
        'messaging_product': 'whatsapp'
    }
    try:
        
        file_content = uploaded_file.read()


        files = {
            'file': ('filename.ext', file_content, media_type)
        }

        
        response = requests.post(url, headers=headers, data=data, files=files)
        return response.json()

    except Exception as e:
        print(f'Error: {e}')
        return {'error': str(e)}
    
def process_media_file(file, phone_number_id, access_token):
    if file:
        file_extension = file.name.split('.')[-1]
        media_type = get_media_format(file_extension)
        print("media_type", media_type)
        response = generate_id(phone_number_id, media_type, file, access_token)
        return str(response.get('id')), str(media_type)
    return None, None