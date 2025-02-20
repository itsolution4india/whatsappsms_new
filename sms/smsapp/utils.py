import datetime
from .models import ScheduledMessage, ReportInfo, BotSentMessages, RegisterApp
from django.utils.timezone import now
from django.utils import timezone
import requests, logging, string, random, json
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
import pandas as pd

logger = logging.getLogger('django')

def expand_times(time_list):
    expanded_times = []
    for time_str in time_list:
        time_obj = datetime.datetime.strptime(time_str, '%H:%M:%S')
        for i in range(3):
            expanded_times.append((time_obj + datetime.timedelta(seconds=i)).strftime('%H:%M:%S'))
    return sorted(set(expanded_times))

def check_schedule_timings(schedule_time, delta_seconds=5):
    scheduled_messages = ScheduledMessage.objects.filter(schedule_date=now().date())
    scheduled_times = scheduled_messages.values_list('schedule_time', flat=True)
    
    scheduled_times = expand_times(scheduled_times)
    schedule_time_obj = datetime.datetime.strptime(schedule_time, '%H:%M:%S')
    scheduled_times_dt = [datetime.datetime.strptime(time, '%H:%M:%S') for time in scheduled_times]
    
    result = []
    if schedule_time in scheduled_times:
        for i in range(3, delta_seconds + 3):
            before_time = schedule_time_obj - datetime.timedelta(seconds=i)
            if before_time not in scheduled_times_dt and len(result) < 5:
                result.append(before_time.strftime('%H:%M:%S'))

            after_time = schedule_time_obj + datetime.timedelta(seconds=i)
            if after_time not in scheduled_times_dt and len(result) < 5:
                result.append(after_time.strftime('%H:%M:%S'))

        return result if result else False
    else:
        return False

class CustomJSONDecoder(json.JSONDecoder):
    def decode(self, s):
        obj = super().decode(s)
        
        if 'screens' in obj and len(obj['screens']) > 0:
            obj['screens'][0]['id'] = 'ITSOLUTION'
            
        def convert_booleans(item):
            if isinstance(item, dict):
                return {k: convert_booleans(v) for k, v in item.items()}
            elif isinstance(item, list):
                return [convert_booleans(i) for i in item]
            elif item == "true":
                return True
            elif item == "false":
                return False
            return item
            
        return convert_booleans(obj)
        
def generate_code():
    digits = random.choices(string.digits, k=6)
    letters = random.choices(string.ascii_uppercase, k=6)
    combined = digits + letters
    random.shuffle(combined)
    return ''.join(combined)

def create_report(current_user, phone_numbers_string, all_contact, template_name):
    report_id = generate_code()
    try:
        ReportInfo.objects.create(
            email=str(current_user),
            campaign_title=report_id,
            contact_list=phone_numbers_string,
            message_date=timezone.now(),
            message_delivery=len(all_contact),
            template_name=template_name
        )
        return report_id
    except Exception as e:
        logger.error(str(e))
        logger.error(f"{str(current_user)}, {report_id}, {phone_numbers_string}, {timezone.now()}, {len(all_contact)}, {template_name}")
        return str(e)

def insert_bot_sent_message(
    token, phone_number_id, contacts, message_type, header, body, footer, 
    button_data, product_data, catalog_id, sections, lat, lon, media_id
):
    # Create a new instance of BotSentMessages
    new_message = BotSentMessages(
        token=token,
        phone_number_id=phone_number_id,
        contact_list=contacts,
        message_type=message_type,
        header=header,
        body=body,
        footer=footer,
        button_data=button_data,
        product_data=product_data,
        catalog_id=catalog_id,
        sections=sections,
        latitude=lat,
        longitude=lon,
        media_id=media_id,
    )
    
    new_message.save()

    return new_message

def get_template_details_by_name(token, waba_id, template_name):
    url = f"https://graph.facebook.com/v14.0/{waba_id}/message_templates"
    
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(url, headers=headers, params={"name": template_name})
    
    if response.status_code == 200:
        templates = response.json()
        for template in templates.get('data', []):
            if template['name'] == template_name:
                return template
        logging.error(f"Template with name {template_name} not found.")
        return None
    else:
        logging.error(f"Failed to get template details. Status code: {response.status_code}")
        logging.error(f"Response: {response.text}")
        return None

def validate_balance(request, total_numbers, category=None):
    marketing_coins = request.user.marketing_coins
    auth_coins = request.user.authentication_coins
    if request.user.email == 'samsungindia@gmail.com':
        category = "MARKETING"
    if category == "MARKETING" and marketing_coins >= total_numbers:
        return True
    elif (category == 'AUTHENTICATION' or category == 'UTILITY') and auth_coins >= total_numbers:
        return True
    else:
        return False
    
def parse_fb_error(data):
    """
    Parse Facebook API error response into a more readable format
    """
    if isinstance(data, dict) and 'error' in data:
        error = data['error']
        error_details = {
            "type": error.get('type', 'Unknown Error'),
            "code": error.get('code', 'N/A'),
            "message": error.get('message', 'No specific message'),
            "user_title": error.get('error_user_title', ''),
            "user_message": error.get('error_user_msg', ''),
            "trace_id": error.get('fbtrace_id', '')
        }
        return error_details
    return {
        "type": "Unknown Error",
        "message": "Unable to parse error details"
    }
    
def get_token_and_app_id(request):
    token = get_object_or_404(RegisterApp, app_name=request.user.register_app).token
    app_id = get_object_or_404(RegisterApp, app_name=request.user.register_app).app_id
    return token, app_id

@login_required
def display_whatsapp_id(request):
    whatsapp_id = request.user.whatsapp_business_account_id
    return whatsapp_id

def display_phonenumber_id(request):
    phonenumber_id = request.user.phone_number_id
    return phonenumber_id
    
def show_discount(user):
    discount=user.discount
    return discount

def make_variables_list(df, valid_numbers):
    try:
        df = df[df['phone_numbers'].isin(valid_numbers)]
        numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
        for col in numeric_cols:
            df[col] = df[col].astype(str)
        
        var_cols_list = df.iloc[:, :].values.tolist()
        return var_cols_list
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        return None
    
def get_template_details(campaign_list, template_name, required_data=None):
    for campaign in campaign_list:
        if campaign['template_name'] == template_name:
            if required_data:
                return campaign[required_data]  
            else:
                return campaign
    return None

def analyize_templates(data):
    total_templates = len(data)
    marketing_templates = 0
    utility_templates = 0
    authentication_templates = 0
    
    for template in data:
        if template['category'] == 'MARKETING':
            marketing_templates += 1
        elif template['category'] == 'UTILITY':
            utility_templates += 1
        elif template['category'] == 'AUTHENTICATION':
            authentication_templates += 1
    return total_templates,marketing_templates,utility_templates,authentication_templates

def count_response(all_replies_dict):
    now = datetime.datetime.now(datetime.timezone.utc)
    start_of_today = datetime.datetime(now.year, now.month, now.day, tzinfo=datetime.timezone.utc)
    last_7_days = now - datetime.timedelta(days=7)
    last_30_days = now - datetime.timedelta(days=30)
    
    today_responses = 0
    last_7_days_responses = 0
    last_30_days_responses = 0
    total_responses = len(all_replies_dict)
    
    for reply in all_replies_dict:
        last_updated = reply['last_updated']
        if last_updated >= start_of_today:
            today_responses += 1
        if last_updated >= last_7_days:
            last_7_days_responses += 1
        if last_updated >= last_30_days:
            last_30_days_responses += 1
    
    return today_responses, last_7_days_responses, last_30_days_responses, total_responses