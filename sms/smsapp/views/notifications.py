from django.shortcuts import render, redirect, get_object_or_404
from ..models import Notifications
from django.urls import reverse
from .auth import username, display_phonenumber_id, display_whatsapp_id

def notifications_list(request):
    notifications = Notifications.objects.filter(email=request.user).order_by('-created_at')

    for notification in notifications:
        if notification.start_request_id != 0 and not notification.end_request_id !=0:
            notification.status = "pending"
        elif notification.end_request_id != 0:
            notification.status = "success"
        else:
            notification.status = "failed"
            
    context = {
            "coins":request.user.marketing_coins + request.user.authentication_coins,
            "marketing_coins":request.user.marketing_coins,
            "authentication_coins":request.user.authentication_coins,
            "username": username(request),
            "WABA_ID": display_whatsapp_id(request),
            "PHONE_ID": display_phonenumber_id(request),
            'notifications': notifications
            }
    return render(request, 'notifications_list.html', context)

def delete_notification(request, pk):
    notification = get_object_or_404(Notifications, pk=pk)
    notification.delete()
    return redirect(reverse('notifications_list'))