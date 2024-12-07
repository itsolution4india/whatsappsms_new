from .auth import check_user_permission, username
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from ..models import ScheduledMessage
from ..utils import display_whatsapp_id, display_phonenumber_id
from django.shortcuts import get_object_or_404
from django.contrib import messages


@login_required
def schedules(request):
    if not check_user_permission(request.user, 'can_schedule_tasks'):
        return redirect("access_denide")
    scheduledmessages = ScheduledMessage.objects.filter(current_user=request.user.email)
    context = {
        "coins":request.user.marketing_coins + request.user.authentication_coins,
        "marketing_coins":request.user.marketing_coins,
        "authentication_coins":request.user.authentication_coins,
        "username":username(request),
        "WABA_ID":display_whatsapp_id(request),
        "PHONE_ID":display_phonenumber_id(request),
        "scheduledmessages": scheduledmessages
    }
    return render(request, "schedules.html", context)

@login_required
def delete_schedule(request, schedule_id):
    scheduled_message = get_object_or_404(ScheduledMessage, id=schedule_id, current_user=request.user.email)
    scheduled_message.delete()
    messages.success(request, "Schedule deleted successfully.")
    return redirect('schedules')