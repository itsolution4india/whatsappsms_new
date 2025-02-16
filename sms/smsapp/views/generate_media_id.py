from django.contrib.auth.decorators import login_required
from ..utils import display_whatsapp_id, display_phonenumber_id, get_token_and_app_id, logger
from django.views.decorators.csrf import csrf_exempt
import requests
from django.shortcuts import render
from .auth import username
from django.http import FileResponse, HttpResponse
from django.views.decorators.http import require_http_methods
import mimetypes
from django.http import JsonResponse

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
        logger.info(f'Error: {e}')
        return {'error': str(e)}

@login_required
@csrf_exempt
def upload_media(request):
    token, _ = get_token_and_app_id(request)
    context={
    "coins":request.user.marketing_coins + request.user.authentication_coins,
    "marketing_coins":request.user.marketing_coins,
    "authentication_coins":request.user.authentication_coins,
    "username":username(request),
    "WABA_ID":display_whatsapp_id(request),
    "PHONE_ID":display_phonenumber_id(request)
    }
    if request.method == 'POST':
        uploaded_file = request.FILES['file']
        file_extension = uploaded_file.name.split('.')[-1]
        phone_number_id=display_phonenumber_id(request)
        media_type = get_media_format(file_extension)
        response = generate_id(phone_number_id, media_type, uploaded_file, token)
        
        print(response)
        return render(request, "media-file.html", {'response': response.get('id'),"username":username(request),"coins":request.user.coins,"WABA_ID":display_whatsapp_id(request),"PHONE_ID":display_phonenumber_id(request)})
    else:
        return render(request, "media-file.html",context)

@login_required
@csrf_exempt
def generatemediaid(request):
    token, _ = get_token_and_app_id(request)
    if request.method == 'POST':
        uploaded_file = request.FILES['file']
        file_extension = uploaded_file.name.split('.')[-1]
        phone_number_id=display_phonenumber_id(request)
        media_type = get_media_format(file_extension)
        response = generate_id(phone_number_id, media_type, uploaded_file, token)
        
        if 'id' in response:
            return JsonResponse({'media_id': response['id']}, status=200)
        else:
            return JsonResponse({'error': 'Failed to generate media ID'}, status=400)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
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

def download_facebook_media(request, media_id):
    access_token, _ = get_token_and_app_id(request)

    # Fetch media URL from Facebook Graph API
    media_url = f'https://graph.facebook.com/v16.0/{media_id}'
    headers = {'Authorization': f'Bearer {access_token}'}

    response = requests.get(media_url, headers=headers)
    if response.status_code != 200:
        return HttpResponse('Failed to get media', status=500)

    media_data = response.json()
    
    download_url = media_data.get('source') or media_data.get('url')
    if not download_url:
        return HttpResponse("No download URL found in the response", status=500)

    # Download the actual media file
    media_response = requests.get(download_url, headers={'Authorization': f'Bearer {access_token}'})
    if media_response.status_code != 200:
        return HttpResponse(f'Failed to download media: {media_response.status_code}', status=500)

    # Determine file extension based on content type
    content_type = media_response.headers.get('Content-Type', '')
    extension = mimetypes.guess_extension(content_type) or '.bin'  # Default to .bin for unknown types
    if content_type.startswith('image'):
        extension = '.jpg'
    elif content_type.startswith('application'):
        extension = '.pdf'
    elif content_type.startswith('video'):
        extension = '.mp4'

    # Prepare the file for download
    filename = f"facebook_media_{media_id}{extension}"
    response = HttpResponse(media_response.content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename={filename}'

    return response