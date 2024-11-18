from datetime import datetime, timedelta
from .models import ScheduledMessage, ReportInfo
from django.utils.timezone import now
import json
import random
import string
from django.utils import timezone
import requests
import logging

def expand_times(time_list):
    expanded_times = []
    for time_str in time_list:
        time_obj = datetime.strptime(time_str, '%H:%M:%S')
        for i in range(3):
            expanded_times.append((time_obj + timedelta(seconds=i)).strftime('%H:%M:%S'))
    return sorted(set(expanded_times))

def check_schedule_timings(schedule_time, delta_seconds=5):
    scheduled_messages = ScheduledMessage.objects.filter(schedule_date=now().date())
    scheduled_times = scheduled_messages.values_list('schedule_time', flat=True)
    
    scheduled_times = expand_times(scheduled_times)
    schedule_time_obj = datetime.strptime(schedule_time, '%H:%M:%S')
    scheduled_times_dt = [datetime.strptime(time, '%H:%M:%S') for time in scheduled_times]
    
    result = []
    if schedule_time in scheduled_times:
        for i in range(3, delta_seconds + 3):
            before_time = schedule_time_obj - timedelta(seconds=i)
            if before_time not in scheduled_times_dt and len(result) < 5:
                result.append(before_time.strftime('%H:%M:%S'))

            after_time = schedule_time_obj + timedelta(seconds=i)
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
        return str(e)
    
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
