from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from ..functions.send_messages import display_phonenumber_id
from ..utils import display_whatsapp_id, get_token_and_app_id, process_response_data, calculate_responses, logger
from .auth import username
from ..models import ReportInfo, BotSentMessages, Last_Replay_Data
import pandas as pd
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from ..fastapidata import send_bot_api
from django.utils import timezone
from django.utils.timezone import make_aware
from django.forms.models import model_to_dict
import datetime
from ..media_id import process_media_file
from .reports import get_user_responses

def update_or_create_reply_data(request, all_replies_grouped):
    for _, row in all_replies_grouped.iterrows():
        existing_record = Last_Replay_Data.objects.filter(
            number=row['contact_wa_id'], user=request.user.email
        ).first()
        max_date = make_aware(row['max_date']) if isinstance(row['max_date'], datetime.datetime) else row['max_date']
        
        if existing_record:
            try:
                if existing_record.last_updated < max_date:
                    if int(row['count']) > int(existing_record.count):
                        if existing_record.status == 'read':
                            count_difference = int(row['count']) - int(existing_record.last_count)
                        else:
                            count_difference = int(row['count'])
                        
                        existing_record.count = str(count_difference)
                        existing_record.name = row['contact_name']
                        existing_record.status = 'unread'
                        existing_record.last_updated=timezone.now()
                        existing_record.last_count = int(row['count'])
                        existing_record.save()
            except Exception as e:
                logger.error(f"Error while updating existing_record {e}")
        else:
            try:
                Last_Replay_Data.objects.create(
                    number=row['contact_wa_id'],
                    user=request.user.email,
                    name=row['contact_name'],
                    count=str(row['count']),
                    last_count=str(row['count']),
                    status='unread',
                    last_updated=timezone.now()
                )
            except Exception as e:
                logger.error(f"Error while creating new record {e}")
                
from django.views.decorators.http import require_http_methods

@login_required
def bot_interactions(request):
    user_status = None
    unique_contact_names = []
    selected_phone = request.GET.get('phone_number', None)
    phone_id = display_phonenumber_id(request)
    combined_data = []
    
    report_list = ReportInfo.objects.filter(email=request.user).values_list('contact_list', flat=True)
    all_phone_numbers = set(phone for report in report_list for phone in report.split(','))
    df = get_user_responses(request)
    # df = pd.read_csv(r"C:\Users\user\Downloads\webhook_responses.csv")
    
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['phone_number_id'] = df['phone_number_id'].astype(str).str.replace(r'\.0$', '', regex=True)
    df['contact_wa_id'] = df['contact_wa_id'].astype(str).str.replace(r'\.0$', '', regex=True)
    
    max_date = df['Date'].max()
    unique_contact_wa_id = set(df['contact_wa_id'].unique())
    
    messages_data = BotSentMessages.objects.filter(phone_number_id=phone_id).values()
    for message in messages_data:
        message['created_at'] = timezone.localtime(message['created_at'], timezone.get_current_timezone())
    messages_df = pd.DataFrame(messages_data)
    messages_df['created_at'] = pd.to_datetime(messages_df['created_at'], errors='coerce')
    
    contact_list = messages_df['contact_list'].tolist()
    matched_numbers = list(set(all_phone_numbers) & unique_contact_wa_id)
    combined_list = [str(num) for sublist in contact_list for num in sublist] + matched_numbers
    matching_phone_numbers = list(set(filter(None, combined_list)))
    all_replies = df[df['contact_wa_id'].isin(matching_phone_numbers)]
    all_replies_grouped = all_replies.groupby(['contact_wa_id', 'contact_name']).agg(
        count=('contact_wa_id', 'size'),  # Count the occurrences
        max_date=('Date', 'max')  # Get the max date
    ).reset_index()
    
    update_or_create_reply_data(request, all_replies_grouped)
    
    last_replay_data = Last_Replay_Data.objects.filter(user=request.user.email).order_by('-last_updated')
    data_as_dict = [
        {**model_to_dict(record), 'created_at': record.created_at.strftime('%Y-%m-%d %H:%M:%S')}
        for record in last_replay_data
    ]
    chart_data = process_response_data(data_as_dict)
    today_responses, last_7_days_responses, _, _ = calculate_responses(chart_data)
    
    combined_data = []
    if selected_phone:
        Last_Replay_Data.objects.filter(
            number=selected_phone,
            user=request.user.email,
        ).update(status='read')
        
        filtered_df = df[
            (df['contact_wa_id'] == selected_phone) & 
            (df['status'] == 'reply')
        ].copy()
        
        filtered_df['Date'] = pd.to_datetime(filtered_df['Date'], errors='coerce')
        max_date = filtered_df['Date'].max()
        current_date = datetime.datetime.now()
        time_difference = current_date - max_date
        if time_difference <= datetime.timedelta(hours=24):
            user_status = "active"
        else:
            user_status = "inactive"
        unique_contact_names = filtered_df['contact_name'].unique()
        for _, row in filtered_df.iterrows():
            record = {
                'source': 'df',
                'Date': row['Date'],
                'display_phone_number': row['display_phone_number'],
                'phone_number_id': row['phone_number_id'],
                'waba_id': row['waba_id'],
                'contact_wa_id': row['contact_wa_id'],
                'status': row['status'],
                'message_timestamp': row['message_timestamp'],
                'error_code': row['error_code'],
                'error_message': row['error_message'],
                'contact_name': row['contact_name'],
                'message_from': row['message_from'],
                'message_type': row['message_type'],
                'message_body': row['message_body'],
            }
            combined_data.append(record)
            
        messages_df = messages_df[messages_df['contact_list'].apply(lambda x: selected_phone in x)]
        for _, row in messages_df.iterrows():
            record = {
                'source': 'messages',
                'id': row['id'],
                'token': row['token'],
                'phone_number_id': row['phone_number_id'],
                'contact_list': row['contact_list'],
                'message_type': row['message_type'],
                'header': row['header'],
                'body': row['body'],
                'footer': row['footer'],
                'button_data': row['button_data'],
                'product_data': row['product_data'],
                'catalog_id': row['catalog_id'],
                'latitude': row['latitude'],
                'longitude': row['longitude'],
                'media_id': row['media_id'],
                'created_at': row['created_at'],
                'sections': row['sections'],
            }
            combined_data.append(record)

        for item in combined_data:
            if 'created_at' in item and item['created_at'] is not None:
                item['created_at'] = item['created_at'].replace(tzinfo=None)

        combined_data = sorted(combined_data, key=lambda x: (x['Date'] if 'Date' in x else x['created_at']))

    total_numbers = matching_phone_numbers
    context = {
        "coins": request.user.marketing_coins + request.user.authentication_coins,
        "marketing_coins": request.user.marketing_coins,
        "authentication_coins": request.user.authentication_coins,
        "username": username(request),
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request),
        "phone_numbers_list": total_numbers,
        "all_replies_dict": data_as_dict,
        "selected_phone": selected_phone,
        "combined_data": combined_data,
        "max_date": max_date,
        "user_status": user_status,
        "today_responses": today_responses,
        "last_7_days_responses": last_7_days_responses,
        "contact_name": unique_contact_names[0] if unique_contact_names else None
    }
    return render(request, "bot_interactions.html", context)

@login_required
@csrf_exempt
def user_interaction(request):
    if request.method == 'POST':
        chat_text = request.POST.get('chat_text', '')
        phone_number = request.POST.get('phone_number', '')
        attachment = request.FILES.get('attachment')
        if chat_text and phone_number:
            token, _ = get_token_and_app_id(request)
            phone_number_id = display_phonenumber_id(request)
            if attachment:
                media_id_one, media_type_one = process_media_file(attachment, phone_number_id, token)
                if media_type_one in ['image/jpeg', 'image/png']:
                    response = send_bot_api(token, phone_number_id, phone_number, "image", body=chat_text, media_id=media_id_one)
                elif media_type_one == "application/pdf":
                    response = send_bot_api(token, phone_number_id, phone_number, "document", body=chat_text, media_id=media_id_one)
                elif media_type_one == "video/mp4":
                    response = send_bot_api(token, phone_number_id, phone_number, "video", body=chat_text, media_id=media_id_one)
                else:
                    return JsonResponse({'status': 'error', 'message': 'File type not supported'})
            else:
                response = send_bot_api(token, phone_number_id, phone_number, "text", body=chat_text)
            return JsonResponse({'status': 'success', 'message': 'Message sent successfully'})
        
        return JsonResponse({'status': 'error', 'message': 'Missing required fields'})
    
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

@login_required
@require_http_methods(["GET"])
def get_phone_numbers_api(request):
    """API endpoint to get phone numbers list"""
    try:
        report_list = ReportInfo.objects.filter(email=request.user).values_list('contact_list', flat=True)
        all_phone_numbers = set(phone for report in report_list for phone in report.split(','))
        df = get_user_responses(request)
        # df = pd.read_csv(r"C:\Users\user\Downloads\webhook_responses.csv")
        
        if not df.empty:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['phone_number_id'] = df['phone_number_id'].astype(str).str.replace(r'\.0$', '', regex=True)
            df['contact_wa_id'] = df['contact_wa_id'].astype(str).str.replace(r'\.0$', '', regex=True)
            
            unique_contact_wa_id = set(df['contact_wa_id'].unique())
            phone_id = display_phonenumber_id(request)
            
            messages_data = BotSentMessages.objects.filter(phone_number_id=phone_id).values()
            messages_df = pd.DataFrame(messages_data)
            
            if not messages_df.empty:
                contact_list = messages_df['contact_list'].tolist()
                matched_numbers = list(set(all_phone_numbers) & unique_contact_wa_id)
                combined_list = [str(num) for sublist in contact_list for num in sublist] + matched_numbers
                matching_phone_numbers = list(set(filter(None, combined_list)))
                
                all_replies = df[df['contact_wa_id'].isin(matching_phone_numbers)]
                all_replies_grouped = all_replies.groupby(['contact_wa_id', 'contact_name']).agg(
                    count=('contact_wa_id', 'size'),
                    max_date=('Date', 'max')
                ).reset_index()
                
                update_or_create_reply_data(request, all_replies_grouped)
                
                last_replay_data = Last_Replay_Data.objects.filter(user=request.user.email).order_by('-last_updated')
                data_as_dict = [
                    {
                        'number': record.number,
                        'name': record.name,
                        'status': record.status,
                        'count': record.count,
                        'created_at': record.created_at.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    for record in last_replay_data
                ]
                
                chart_data = process_response_data(data_as_dict)
                today_responses, last_7_days_responses, _, _ = calculate_responses(chart_data)
                
                return JsonResponse({
                    'status': 'success',
                    'phone_numbers': data_as_dict,
                    'today_responses': today_responses,
                    'last_7_days_responses': last_7_days_responses
                })
        
        return JsonResponse({
            'status': 'success',
            'phone_numbers': [],
            'today_responses': 0,
            'last_7_days_responses': 0
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })

@login_required
@require_http_methods(["GET"])
def get_conversation_api(request):
    """API endpoint to get conversation for a specific phone number"""
    try:
        selected_phone = request.GET.get('phone_number')
        if not selected_phone:
            return JsonResponse({
                'status': 'error',
                'message': 'Phone number is required'
            })
        
        # Mark messages as read
        Last_Replay_Data.objects.filter(
            number=selected_phone,
            user=request.user.email,
        ).update(status='read')
        
        df = get_user_responses(request)
        # df = pd.read_csv(r"C:\Users\user\Downloads\webhook_responses.csv")
        phone_id = display_phonenumber_id(request)
        
        # Get user replies
        filtered_df = df[
            (df['contact_wa_id'] == selected_phone) & 
            (df['status'] == 'reply')
        ].copy()
        
        # Determine user status
        user_status = "inactive"
        if not filtered_df.empty:
            filtered_df['Date'] = pd.to_datetime(filtered_df['Date'], errors='coerce')
            max_date = filtered_df['Date'].max()
            current_date = datetime.datetime.now()
            time_difference = current_date - max_date
            if time_difference <= datetime.timedelta(hours=24):
                user_status = "active"
        
        # Get bot messages
        messages_data = BotSentMessages.objects.filter(phone_number_id=phone_id).values()
        for message in messages_data:
            message['created_at'] = timezone.localtime(message['created_at'], timezone.get_current_timezone())
        messages_df = pd.DataFrame(messages_data)
        
        if not messages_df.empty:
            messages_df = messages_df[messages_df['contact_list'].apply(lambda x: selected_phone in x)]
        
        # Combine data
        combined_data = []
        
        # Add user replies
        for _, row in filtered_df.iterrows():
            record = {
                'source': 'df',
                'Date': row['Date'].isoformat() if pd.notna(row['Date']) else None,
                'display_phone_number': row['display_phone_number'],
                'phone_number_id': row['phone_number_id'],
                'waba_id': row['waba_id'],
                'contact_wa_id': row['contact_wa_id'],
                'status': row['status'],
                'message_timestamp': row['message_timestamp'],
                'error_code': row['error_code'],
                'error_message': row['error_message'],
                'contact_name': row['contact_name'],
                'message_from': row['message_from'],
                'message_type': row['message_type'],
                'message_body': row['message_body'],
            }
            combined_data.append(record)
        
        # Add bot messages
        if not messages_df.empty:
            for _, row in messages_df.iterrows():
                record = {
                    'source': 'messages',
                    'id': row['id'],
                    'token': row['token'],
                    'phone_number_id': row['phone_number_id'],
                    'contact_list': row['contact_list'],
                    'message_type': row['message_type'],
                    'header': row['header'],
                    'body': row['body'],
                    'footer': row['footer'],
                    'button_data': row['button_data'],
                    'product_data': row['product_data'],
                    'catalog_id': row['catalog_id'],
                    'latitude': row['latitude'],
                    'longitude': row['longitude'],
                    'media_id': row['media_id'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'sections': row['sections'],
                }
                combined_data.append(record)
        
        # Sort by timestamp
        for item in combined_data:
            if 'created_at' in item and item['created_at'] is not None:
                item['created_at'] = item['created_at'].replace('T', ' ').replace('Z', '')
        
        combined_data = sorted(combined_data, key=lambda x: (
            x['Date'] if 'Date' in x and x['Date'] else 
            x['created_at'] if 'created_at' in x and x['created_at'] else 
            '1970-01-01 00:00:00'
        ))
        
        return JsonResponse({
            'status': 'success',
            'user_status': user_status,
            'messages': combined_data,
            'contact_name': filtered_df['contact_name'].iloc[0] if not filtered_df.empty else None
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def send_message_api(request):
    """API endpoint to send a message"""
    try:
        chat_text = request.POST.get('chat_text', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        attachment = request.FILES.get('attachment')
        
        if not chat_text:
            return JsonResponse({
                'status': 'error',
                'message': 'Message text is required'
            })
        
        if not phone_number:
            return JsonResponse({
                'status': 'error',
                'message': 'Phone number is required'
            })
        
        # Check if user has enough coins
        total_coins = request.user.marketing_coins + request.user.authentication_coins
        if total_coins <= 0:
            return JsonResponse({
                'status': 'error',
                'message': 'Insufficient coins to send message'
            })
        
        # Process the message sending logic here
        # This is where you would integrate with your existing message sending logic
        
        # For demonstration, here's a basic structure:
        try:
            # Your existing message sending logic
            phone_id = display_phonenumber_id(request)
            waba_id = display_whatsapp_id(request)
            
            # Handle attachment if present
            media_id = None
            if attachment:
                # Your media upload logic here
                # media_id = upload_media_to_whatsapp(attachment)
                pass
            
            # Send the message
            message_data = {
                'phone_number_id': phone_id,
                'contact_list': [phone_number],
                'message_type': 'text',
                'body': chat_text,
                'created_at': timezone.now()
            }
            
            if media_id:
                message_data['media_id'] = media_id
                message_data['message_type'] = 'image' if attachment.content_type.startswith('image/') else 'document'
            
            # Save to database
            bot_message = BotSentMessages.objects.create(**message_data)
            
            # Deduct coins
            if request.user.marketing_coins > 0:
                request.user.marketing_coins -= 1
            elif request.user.authentication_coins > 0:
                request.user.authentication_coins -= 1
            request.user.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Message sent successfully',
                'message_id': bot_message.id,
                'remaining_coins': request.user.marketing_coins + request.user.authentication_coins
            })
            
        except Exception as send_error:
            return JsonResponse({
                'status': 'error',
                'message': f'Failed to send message: {str(send_error)}'
            })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })