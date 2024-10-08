from datetime import datetime, timedelta
from .models import ScheduledMessage
from django.utils.timezone import now

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
