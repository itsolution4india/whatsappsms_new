from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from ..models import ReportInfo,Templates, ScheduledMessage, CountryPermission, Whitelist_Blacklist, Group, Contact,CustomUser,LoginHistory,RegisterApp,CoinsHistory
from ..media_id import get_media_format,generate_id
from django.contrib import messages
from django.contrib.auth.tokens import default_token_generator
import json, re, openpyxl
from ..functions.template_msg import fetch_templates
from django.utils.timezone import now
from ..functions.send_messages import send_messages, display_phonenumber_id, save_schedule_messages
from ..utils import  get_token_and_app_id, display_whatsapp_id, logger
from .auth import check_user_permission
from ..functions.flows import send_flow_messages_with_report, send_carousel_messages_with_report
from .reports import get_latest_rows_by_contacts, get_unique_phone_numbers
from ..fastapidata import send_validate_req, send_carousel_message_api
import pandas as pd
from ..media_id import process_media_file
import time
from django.contrib.auth import update_session_auth_hash
from django.db.models import Sum
from django.views import View
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.tokens import default_token_generator




class UserProfileView(LoginRequiredMixin, View):
    template_name = "profile.html"

    def get(self, request, *args, **kwargs):
        user = request.user

        # Handle AJAX token request
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return self.handle_ajax_token(request)

        # Normal GET request
        token = user.api_token or get_token_and_app_id(request)[0]
        
        total_credit = CoinsHistory.objects.filter(user=request.user, type=CoinsHistory.CREDIT).aggregate(
        total=Sum('number_of_coins')
        )['total'] or 0

        total_debit = CoinsHistory.objects.filter(user=request.user, type=CoinsHistory.DEBIT).aggregate(
            total=Sum('number_of_coins')
        )['total'] or 0
                
      

        context = {
            'username': user.username,
            'coins': user.marketing_coins + user.authentication_coins,
            'token': token,
            'marketing_coins': user.marketing_coins,
            'authentication_coins': user.authentication_coins,
            'WABA_ID': display_whatsapp_id(request),
            'PHONE_ID': display_phonenumber_id(request),
            'total_credit': total_credit,
            'total_debit': total_debit,
          
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        user = request.user
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not user.check_password(old_password):
            messages.error(request, "The old password is incorrect.")
            return redirect('profileuser')

        if new_password != confirm_password:
            messages.error(request, "New password and confirm password do not match.")
            return redirect('profileuser')

        user.set_password(new_password)
        user.save()

        user = CustomUser.objects.get(email=user.email)
        user.password2 = new_password
        user.save()

        update_session_auth_hash(request, user)
        messages.success(request, "Password changed successfully.")
        return redirect('profileuser')

    def handle_ajax_token(self, request):
        try:
            user = CustomUser.objects.get(email=request.user.email)
            token = default_token_generator.make_token(user)
            user.api_token = token
            user.save()
            return JsonResponse({'token': token})
        except CustomUser.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)

