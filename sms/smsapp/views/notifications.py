from django.shortcuts import render, redirect, get_object_or_404
from ..models import Notifications, ReportInfo
from django.urls import reverse
from .auth import username, display_phonenumber_id, display_whatsapp_id
from datetime import datetime, timedelta, timezone
from django.core.paginator import Paginator
from itertools import chain
from operator import attrgetter

def process_status(item, current_time):
    """Helper function to process status for both notifications and reports"""
    time_difference = current_time - item.created_at
    
    if item.start_request_id != "0" and item.end_request_id != "0":
        return "success"
    elif item.start_request_id != "0" and item.end_request_id == "0" and time_difference < timedelta(hours=1):
        return "pending"
    else:
        return "failed"
    
def process_report_status(item, current_time):
    """Helper function to process status for both notifications and reports"""
    time_difference = current_time - item.created_at
    
    if item.start_request_id != 0 and item.end_request_id != 0:
        return "success"
    elif item.start_request_id != 0 and item.end_request_id == 0 and time_difference < timedelta(hours=1):
        return "pending"
    else:
        return "failed"

def get_notification_type(request_id):
    """Helper function to determine notification type"""
    if not request_id or request_id == "0":
        return "Unknown"
    
    type_mapping = {
        "MESSAGE": "Message request",
        "FLOW": "Flow message request",
        "CAROUSEL": "Carousel message request"
    }
    
    for prefix, notification_type in type_mapping.items():
        if request_id.startswith(prefix):
            return notification_type
    return "Get report request"

def notifications_list(request):
    notifications = Notifications.objects.filter(email=request.user).order_by('-created_at')
    reports = ReportInfo.objects.filter(email=request.user).exclude(start_request_id=0).order_by('-created_at')
    
    current_time = datetime.now(timezone.utc)

    for notification in notifications:
        notification.status = process_status(notification, current_time)
        notification.type = get_notification_type(notification.request_id)
        notification.is_notification = True
        
    for report in reports:
        report.status = process_report_status(report, current_time)
        report.type = "Report"
        report.is_notification = False
        report.request_id = str(report.start_request_id)
        report.text = ""

    combined_items = sorted(
        chain(notifications, reports),
        key=attrgetter('created_at'),
        reverse=True
    )

    # Apply pagination
    paginator = Paginator(combined_items, 10)  # 10 items per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "coins": request.user.marketing_coins + request.user.authentication_coins,
        "marketing_coins": request.user.marketing_coins,
        "authentication_coins": request.user.authentication_coins,
        "username": username(request),
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request),
        "notifications": page_obj,  # use page_obj instead of full list
    }
    return render(request, 'notifications_list.html', context)

def delete_notification(request, pk):
    notification = get_object_or_404(Notifications, pk=pk)
    notification.delete()
    return redirect(reverse('notifications_list'))