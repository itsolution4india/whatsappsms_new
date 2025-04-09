from .auth import check_user_permission, username
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from ..models import ScheduledMessage
from ..utils import display_whatsapp_id, display_phonenumber_id
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

@login_required
def schedules(request):
    if not check_user_permission(request.user, 'can_schedule_tasks'):
        return redirect("access_denide")
    
    # Get start and end date filters from request
    start_date = request.GET.get('start_date', None)
    end_date = request.GET.get('end_date', None)
    
    # Base queryset
    scheduledmessages = ScheduledMessage.objects.filter(
        current_user=request.user.email
    ).exclude(admin_schedule=True)
    
    # Apply date filters if provided
    if start_date:
        scheduledmessages = scheduledmessages.filter(schedule_date__gte=start_date)
    if end_date:
        scheduledmessages = scheduledmessages.filter(schedule_date__lte=end_date)
    
    # Order messages - pending first, then by date
    scheduledmessages = scheduledmessages.order_by('is_sent', '-schedule_date', '-schedule_time')
    
    # Pagination
    paginator = Paginator(scheduledmessages, 8)  # Show 8 items per page
    page_number = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.get_page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)
    
    context = {
        "coins": request.user.marketing_coins + request.user.authentication_coins,
        "marketing_coins": request.user.marketing_coins,
        "authentication_coins": request.user.authentication_coins,
        "username": username(request),
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request),
        "scheduledmessages": page_obj,
        "start_date": start_date,
        "end_date": end_date
    }
    return render(request, "schedules.html", context)

@login_required
def delete_schedule(request, schedule_id):
    scheduled_message = get_object_or_404(ScheduledMessage, id=schedule_id, current_user=request.user.email)
    scheduled_message.delete()
    messages.success(request, "Schedule deleted successfully.")
    return redirect('schedules')