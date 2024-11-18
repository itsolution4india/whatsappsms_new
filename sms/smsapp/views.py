
from django.shortcuts import render, redirect, HttpResponse
from django.http import HttpResponse
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import authenticate, login
from django.core.exceptions import ObjectDoesNotExist
from .models import CustomUser, RegisterApp, ScheduledMessage, TemplateLinkage, MessageResponse, CoinsHistory, Flows
from django.conf import settings
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required
from .forms import UserLoginForm
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .campaignmail import send_email_change_notification
import logging
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.http import HttpResponseForbidden
from .models import ReportInfo,Templates, UserAccess
from django.contrib.auth import logout
from django.utils import timezone
import requests
logger = logging.getLogger(__name__)
from datetime import datetime, timedelta
from django.db.models import Sum
from django.views.decorators.csrf import csrf_exempt
from .display_templates import fetch_templates
from .media_id import get_media_format,generate_id, process_media_file
from .send_message import send_messages_api
from .create_template import template_create, create_auth_template
# from .message_id import generate_pattern
import openpyxl 
from .models import Whitelist_Blacklist
from django.contrib import messages
from django.http import request
from django.http import FileResponse, Http404
import os
from django.conf import settings 
from .forms import UserLoginForm  
import threading
import json
import ast
import random
import time
from .campaign_media_id import header_handle
#from .smsapi import send_api
from .fastapidata import send_api, send_flow_message_api, send_bot_api
from django.utils.timezone import now
from .functions.flows import create_message_template_with_flow, send_flow_messages_with_report, get_template_type, get_flow_id, get_flows
from .functions.send_messages import send_messages, display_phonenumber_id, save_schedule_messages, schedule_subtract_coins
from .utils import check_schedule_timings, CustomJSONDecoder, create_report
from .functions.template_msg import delete_whatsapp_template
import pandas as pd

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

def check_user_permission(user, permission):
    """Helper function to check a specific permission for a user."""
    try:
        user_access = UserAccess.objects.get(user=user)
        return getattr(user_access, permission, False)
    except UserAccess.DoesNotExist:
        return False

@login_required
def access_denide(request):
    return render(request, "access_denide.html") 

@csrf_exempt
def user_login(request):
    if request.method == "POST":
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username_or_email = form.cleaned_data["username_or_email"]
            password = form.cleaned_data["password"]
            user = None
            if '@' in username_or_email:
                try:
                    user = CustomUser.objects.get(email=username_or_email)
                except CustomUser.DoesNotExist:
                    user = None
            else:
                try:
                    user = CustomUser.objects.get(username=username_or_email)
                except CustomUser.DoesNotExist:
                    user = None

            if user and user.check_password(password):
                login(request, user)
                logger.info(f"User {username_or_email} logged in successfully.")
                return redirect("dashboard")
            else:
                logger.warning(f"Failed login attempt for {username_or_email}")
                form.add_error(None, "Invalid email/username or password.")
        else:
            logger.warning(f"Invalid form submission: {form.errors}")

    else:
        form = UserLoginForm()

    return render(request, "login.html", {"form": form})

def get_token_and_app_id(request):
    token = get_object_or_404(RegisterApp, app_name=request.user.register_app).token
    app_id = get_object_or_404(RegisterApp, app_name=request.user.register_app).app_id
    return token, app_id

@login_required
def username(request):
    username=request.user
    
    return username
@login_required
def display_whatsapp_id(request):
    whatsapp_id = request.user.whatsapp_business_account_id
    return whatsapp_id
    
    
@login_required
def logout_view(request):
    logout(request)
    return redirect("login")

@login_required
def user_dashboard(request):
    context={
    "coins":request.user.coins,
    "username":username(request),
    "WABA_ID":display_whatsapp_id(request),
     "PHONE_ID":display_phonenumber_id(request)
    }
    return render(request, "dashboard.html",context)
    
def show_discount(user):
    discount=user.discount
    return discount
################
@login_required
def Send_Sms(request):
    if not check_user_permission(request.user, 'can_send_sms'):
        return redirect("access_denide")
    ip_address = request.META.get("REMOTE_ADDR", "Unknown IP")
    token, _ = get_token_and_app_id(request)
    current_user = request.user
    
    scheduled_messages = ScheduledMessage.objects.filter(schedule_date=now().date())
    scheduled_times = scheduled_messages.values_list('schedule_time', flat=True)
    
    try:
        coins = request.user.coins
        report_list = ReportInfo.objects.filter(email=request.user)
        template_database = Templates.objects.filter(email=request.user)
        template_value = list(template_database.values_list('templates', flat=True))
        
        # Assuming fetch_templates and display_whatsapp_id are defined elsewhere
        campaign_list = fetch_templates(display_whatsapp_id(request), token)
        if campaign_list is None :
            campaign_list=[]
        templates = [campaign for campaign in campaign_list if campaign['template_name'] in template_value]

        context = {
            "template_name": [template['template_name'] for template in templates],
            "template_data": json.dumps([template['template_data'] for template in templates]),
            "template_status": json.dumps([template['status'] for template in templates]),
            "template_button": json.dumps([json.dumps(template['button']) for template in templates]),
            "template_media": json.dumps([template.get('media_type', 'No media available') for template in templates]),
            "scheduled_times": scheduled_times
        }
    except Exception as e:
        logger.error(f"Error fetching templates: {e}")
        context = {
            "template_name": [],
            "template_data": json.dumps([]),
            "template_status": json.dumps([]),
            "template_button": json.dumps([]),
            "template_media": json.dumps([]),
            "scheduled_times": scheduled_times
        }

    context.update({
        "ip_address": ip_address,
        "coins": coins if 'coins' in locals() else None,
        "report_list": report_list,
        "campaign_list": campaign_list,
        "username": request.user.email if request.user.is_authenticated else None,
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request)
    })

    if request.method == "POST":
        try:
            submitted_variables = []
            if not request.user.is_authenticated:
                
                messages.error(request, "User is not authenticated.")
                return render(request, "send-sms.html", context)

            campaign_title = request.POST.get("campaign_title")
            template_name = request.POST.get("params")
            for key in request.POST:
                if key.startswith('variable'):
                    submitted_variables.append(request.POST[key])
                    
            media_file = request.FILES.get('file', None)
            if media_file:
                file_extension = media_file.name.split('.')[-1]
                media_type = get_media_format(file_extension)
                media_id = generate_id(display_phonenumber_id(request), media_type, media_file, token) 
                media_id = media_id['id']
            else:
                media_id = None
            uploaded_file = request.FILES.get("files", None)
            contacts = request.POST.get("contact_number", "").strip()

            action_type = request.POST.get("action_type")

            if not campaign_title or not template_name:
                messages.error(request, "Campaign title and template name are required.")
                return render(request, "send-sms.html", context)
         
            discount = show_discount(request.user)
            all_contact, contact_list = validate_phone_numbers(request,contacts, uploaded_file, discount)
            
            if action_type == "submit":
                send_messages(current_user, token, display_phonenumber_id(request), campaign_list, template_name, media_id, all_contact, contact_list, campaign_title, request, submitted_variables)
            else:
                schedule_date = request.POST.get("schedule_date")
                schedule_time = request.POST.get("schedule_time")
                result = check_schedule_timings(schedule_time)
                if result:
                    messages.warning(request, f"The time {schedule_time}, is busy. Please choose from these available options: {result}")
                else:
                    messages.success(request, "Message Scheduled Successfully")
                    save_schedule_messages(current_user, template_name, media_id, all_contact, contact_list, campaign_title, schedule_date, schedule_time, submitted_variables)
                    
            return redirect('send-sms')
        except Exception as e:
            logger.error(f"Error processing form: {e}")
            messages.error(request, "There was an error processing your request.")
            return render(request, "send-sms.html", context)

    return render(request, "send-sms.html", context)

##################
#Valid _and _ Duplicate method
import re
def validate_phone_numbers(request,contacts, uploaded_file,discount):
    valid_numbers = set()
    pattern = re.compile(r'^(\+91[\s-]?)?[0]?(91)?[6789]\d{9}$')

    # Parse contacts from POST request
    if contacts:
        numbers_list = set(contacts.split("\r\n"))
    else:
        numbers_list = set()
    '''
    # Parse contacts from uploaded file
    if uploaded_file:
        file_content = uploaded_file.read()
        for line in file_content.splitlines():
            phone_number = line.strip().decode('utf-8')
            numbers_list.add(phone_number) '''
           
    if uploaded_file:
        workbook = openpyxl.load_workbook(uploaded_file)
        sheet = workbook.active
        for row in sheet.iter_rows(min_col=1, max_col=1, min_row=1):
            for cell in row:
                if cell.value is not None:
                    numbers_list.add(str(cell.value).strip())

    # Validate phone numbers
    for phone_number in numbers_list:
        if pattern.match(phone_number):
            valid_numbers.add(phone_number)
            
   
    whitelist_number,blacklist_number=whitelist_blacklist(request)
    def fnn(valid_numbers,discount):
        discount1=(len(valid_numbers)*discount)//100
        return discount1
    def whitelist(valid_numbers, whitelist_number, blacklist_numbers, discount):
        final_list = []
        
        for i in valid_numbers:
            if i in whitelist_number and i not in blacklist_numbers:
                final_list.append(i)
        count = 0
        for j in valid_numbers:
            if j not in whitelist_number and j not in blacklist_numbers:
                count+=1
                if count > discount:
                    final_list.append(j)
                else:
                    continue
        return final_list
    
    valid_numbers=list(valid_numbers)
    if len(valid_numbers)>100:
        discount=discount
    else:
        discount=0
        phone_numbers_string = ",".join(valid_numbers)
        Whitelist_Blacklist.objects.create(
        email=request.user,
        whitelist_phone=phone_numbers_string
        )

    discountnumber=fnn(valid_numbers,discount)
    logging.info(f"discount {discount}")
    logging.info(f"discountnumber {discountnumber}")
    final_list=whitelist(valid_numbers,whitelist_number,blacklist_number,discountnumber)
    

    return valid_numbers, final_list

####################
@login_required
def Campaign(request):
    if not check_user_permission(request.user, 'can_manage_campaign'):
        return redirect("access_denide")
    token, app_id = get_token_and_app_id(request)
    campaign_list = fetch_templates(display_whatsapp_id(request), token)
    if campaign_list is None :
        campaign_list=[]
    template_database = Templates.objects.filter(email=request.user)
    template_value = list(template_database.values_list('templates', flat=True))
    templates = [campaign_list[i] for i in range(len(campaign_list)) if campaign_list[i]['template_name'] in template_value]

    context = {
        "template_value": template_value,
        "coins": request.user.coins,
        "username": username(request),
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request),
        "campaign_list": templates,
        
    }

    if request.method == 'POST':
        template_name = request.POST.get('template_name')
        language = request.POST.get('language')
        category = request.POST.get('category')
        header_type = request.POST.get('actionHeaderType')
        header_content = None
        submitted_variables = []
        for key in request.POST:
                if key.startswith('var_input'):
                    submitted_variables.append(request.POST[key])
                    
        if header_type == 'headerText':
            header_content = request.POST.get('headerText', None)
        elif header_type == 'headerImage':
            header_content = request.FILES.get('headerImage', None)
        elif header_type == 'headerVideo':
            header_content = request.FILES.get('headerVideo', None)
        elif header_type == 'headerDocument':
            header_content = request.FILES.get('headerDocument', None)
        elif header_type == 'headerDocument':
            header_content = request.FILES.get('headerAudio', None)
        
        body_text = request.POST.get('template_data').replace('\n', '\n').replace('<b>', '*').replace('</b>', '*')
        footer_text = request.POST.get('footer_data')
        call_button_text = request.POST.get('callbutton', None)
        phone_number = request.POST.get('contactNumber', None)
        quick_reply_one = request.POST.get('quick_reply_one', None)
        quick_reply_two = request.POST.get('quick_reply_two', None)
        quick_reply_three = request.POST.get('quick_reply_three', None)
        url_button_text = request.POST.get('websitebutton', None)
        website_url = request.POST.get('websiteUrl')
        linked_temp_one = request.POST.get('linked_temp_one', None)
        linked_temp_two = request.POST.get('linked_temp_two', None)
        linked_temp_three = request.POST.get('linked_temp_three', None)

        media_file_one = request.FILES.get('file_one', None)
        media_file_two = request.FILES.get('file_two', None)
        media_file_three = request.FILES.get('file_three', None)

        if media_file_one:
            media_id_one, media_type_one = process_media_file(media_file_one, display_phonenumber_id(request), token)
            time.sleep(1.5) 
        else:
            media_id_one, media_type_one = None, None

        if media_file_two:
            media_id_two, media_type_two = process_media_file(media_file_two, display_phonenumber_id(request), token)
            time.sleep(1.5) 
        else:
            media_id_two, media_type_two = None, None

        if media_file_three:
            media_id_three, media_type_three = process_media_file(media_file_three, display_phonenumber_id(request), token)
        else:
            media_id_three, media_type_three = None, None

        media_id_one = media_id_one + '|' + media_type_one if media_id_one else None
        media_id_two = media_id_two + '|' + media_type_two if media_id_two else None
        media_id_three = media_id_three + '|' + media_type_three if media_id_three else None

        print("IDs", media_id_one, media_id_two, media_id_three)
        if header_type in ['headerImage','headerVideo','headerDocument','headerAudio']:
            header_content = header_handle(header_content, token, app_id)
        
        if quick_reply_one and linked_temp_one:
            TemplateLinkage.objects.create(template_name=template_name, linked_template_name=linked_temp_one, button_name=quick_reply_one, useremail=request.user.email, image_id=media_id_one)

        if quick_reply_two and linked_temp_two:
            TemplateLinkage.objects.create(template_name=template_name, linked_template_name=linked_temp_two, button_name=quick_reply_two, useremail=request.user.email, image_id=media_id_two)

        if quick_reply_three and linked_temp_three:
            TemplateLinkage.objects.create(template_name=template_name, linked_template_name=linked_temp_three, button_name=quick_reply_three, useremail=request.user.email, image_id=media_id_three)
            
        try:
            if category == 'Authentication':
                status, response = create_auth_template(
                    waba_id=display_whatsapp_id(request),
                    access_token=token,
                    template_name=template_name,
                    languages=language
                )
                print(response)
            else:
                status,data=template_create(
                    token=token,
                    waba_id=display_whatsapp_id(request),
                    template_name=template_name,
                    language=language,
                    category=category,
                    header_type=header_type,
                    header_content=header_content,
                    body_text=body_text,
                    footer_text=footer_text,
                    call_button_text=call_button_text,
                    phone_number=phone_number,
                    url_button_text=url_button_text,
                    website_url=website_url,
                    quick_reply_one=quick_reply_one,
                    quick_reply_two=quick_reply_two,
                    quick_reply_three=quick_reply_three,
                    body_example_values = submitted_variables if submitted_variables else None
                )
            if status !=200:
                data_str=str(data)
                return HttpResponse(data_str)

            Templates.objects.create(email=request.user, templates=template_name)
            return redirect('campaign')
        except IntegrityError:
            
            return render(request, "Campaign.html", context)
        
    return render(request, "Campaign.html", context)

####################
# @login_required
# def delete_campaign(request, template_id):
#     if template_id is None:
#         return 
#     campaign_data = get_object_or_404(CampaignData, template_id=template_id)
#     campaign_data.delete()
#     return redirect('campaign')
import csv
@login_required
def Reports(request):
    if not check_user_permission(request.user, 'can_view_reports'):
        return redirect("access_denide")
    try:
        # Fetch data and prepare context
        #campaign_list = fetch_templates(display_whatsapp_id(request))
        template_database = Templates.objects.filter(email=request.user)
        template_value = list(template_database.values_list('templates', flat=True))
        report_list = ReportInfo.objects.filter(email=request.user)
        context = {
            "template_names": template_value,
            "coins": request.user.coins,
            "username": username(request),
            "WABA_ID": display_whatsapp_id(request),
            "PHONE_ID": display_phonenumber_id(request),
            "report_list":report_list
            }
        

        return render(request, "reports.html", context)
    except Exception as e:
        
        return render(request, "reports.html", context)
############
import mysql.connector
import csv
import os
import copy
'''
@login_required
def download_campaign_report(request, report_id):
    try:
        # Fetch the specific report based on the report_id
        report = get_object_or_404(ReportInfo, id=report_id)
        Phone_ID = display_phonenumber_id(request)  # Ensure phone_number_id is defined
        contacts = report.contact_list.split('\r\n')
        contact_all = [phone.strip() for contact in contacts for phone in contact.split(',')]

        # Connect to the database
        connection = mysql.connector.connect(
            host="localhost",
            port=3306,
            user="fedqrbtb_wtsdealnow",
            password="Solution@97",
            database="fedqrbtb_report"
        )
        cursor = connection.cursor()
        query = "SELECT * FROM webhook_responses"
        cursor.execute(query)
        rows = cursor.fetchall()

        # Create a dictionary for quick lookup
        rows_dict = {(row[2], row[4]): row for row in rows}
        matched_rows = []
        
        non_reply_rows=[]
        
        if len(contact_all) >99:
            non_reply_rows = [row for row in rows if row[5] != "reply"]
        else:
            non_reply_rows=[]

        for phone in contact_all:
            matched = False
            row = rows_dict.get((Phone_ID, phone), None)
            print(row)
            if row:
                matched_rows.append(row)
                matched = True

            if not matched and non_reply_rows:
                new_row = copy.deepcopy(random.choice(non_reply_rows))
                new_row_list = list(new_row)
                new_row_list[4] = phone  
                new_row_tuple = tuple(new_row_list)
                matched_rows.append(new_row_tuple)

        cursor.close()
        connection.close()

        # Define your header
        header = "Date,display_phone_number,phone_number_id,waba_id,contact_wa_id,status,message_timestamp,error_code,error_message,contact_name,message_from,message_type,message_body".split(',')

        # Remove duplicates if any
        #matched_rows = list(set(matched_rows))

        # Generate CSV as HttpResponse (stream the file)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{report.campaign_title}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(header)  # Write header
        writer.writerows(matched_rows)  # Write rows
        
        return response
    
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        messages.error(request, "Database error occurred.")
        return redirect('reports')

    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        messages.error(request, f"Error: {str(e)}")
        return redirect('reports')
        '''

@login_required
def download_campaign_report(request, report_id, insight=False):
    try:
        # Fetch the specific report based on the report_id
        report = get_object_or_404(ReportInfo, id=report_id)
        Phone_ID = display_phonenumber_id(request)  # Ensure phone_number_id is defined
        contacts = report.contact_list.split('\r\n')
        contact_all = [phone.strip() for contact in contacts for phone in contact.split(',')]

        # Connect to the database
        connection = mysql.connector.connect(
            host="localhost",
            port=3306,
            user="fedqrbtb_wtsdealnow",
            password="Solution@97",
            database="fedqrbtb_report"
        )
        cursor = connection.cursor()
        query = "SELECT * FROM webhook_responses"
        cursor.execute(query)
        rows = cursor.fetchall()

        # Create a dictionary for quick lookup
        rows_dict = {(row[2], row[4]): row for row in rows}
        
        matched_rows = []
        non_reply_rows = []

    
        if len(contact_all) > 100:
            non_reply_rows = [row for row in rows if row[5] != "reply" and row[2] == Phone_ID]
        
        for phone in contact_all:
            matched = False
            row = rows_dict.get((Phone_ID, phone), None)
            if row:
                matched_rows.append(row)
                matched = True

            if not matched and non_reply_rows:
                new_row = copy.deepcopy(random.choice(non_reply_rows))
                new_row_list = list(new_row)
                new_row_list[4] = phone  # Update the phone number
                new_row_tuple = tuple(new_row_list)
                matched_rows.append(new_row_tuple)
        
        cursor.close()
        connection.close()

        # Define your header
        header = [
            "Date", "display_phone_number", "phone_number_id", "waba_id", "contact_wa_id",
            "status", "message_timestamp", "error_code", "error_message", "contact_name",
            "message_from", "message_type", "message_body"
        ]

        df = pd.DataFrame(matched_rows, columns=header)
        status_counts_df = df['status'].value_counts().reset_index()
        status_counts_df.columns = ['status', 'count']
        total_unique_contacts = len(df['contact_wa_id'].unique())
        total_row = pd.DataFrame([['Total Contacts', total_unique_contacts]], columns=['status', 'count'])
        status_counts_df = pd.concat([status_counts_df, total_row], ignore_index=True)

        # Generate CSV as HttpResponse (stream the file)
        if insight:
            return status_counts_df
        else:
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{report.campaign_title}.csv"'
            
            writer = csv.writer(response)
            writer.writerow(header)  # Write header
            writer.writerows(matched_rows)  # Write rows
            
            return response
    
    except mysql.connector.Error as err:
        logger.error(f"Database error: {err}")
        messages.error(request, "Database error occurred.")
        return redirect('reports')

    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        messages.error(request, f"Error: {str(e)}")
        return redirect('reports')

@login_required
def get_report_insight(request, report_id):
    try:
        insight_data = download_campaign_report(request, report_id, insight=True)
        return JsonResponse({
            'status': 'success',
            'data': insight_data.to_dict('records')
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

##############
@login_required
def whitelist_blacklist(request):
    
    whitelist_blacklists = Whitelist_Blacklist.objects.all()
    whitelist_phones = [obj.whitelist_phone for obj in whitelist_blacklists]
    whitelist_phones_cleaned = [phone for sublist in whitelist_phones for phone in sublist.split('\r\n')]
    whitelist_phone_numbers = [phone.strip() for sublist in whitelist_phones_cleaned for phone in sublist.split(',')]

    blacklist_phones = [obj.blacklist_phone for obj in whitelist_blacklists]
    blacklist_phones_cleaned = [phone for sublist in blacklist_phones for phone in sublist.split('\r\n')]
    blacklist_phone_numbers = [phone.strip() for sublist in blacklist_phones_cleaned for phone in sublist.split(',')]
    

    return whitelist_phone_numbers ,blacklist_phone_numbers


@login_required
@csrf_exempt
def upload_media(request):
    token, _ = get_token_and_app_id(request)
    context={
    "coins":request.user.coins,
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
        
       
        return render(request, "media-file.html", {'response': response.get('id'),"username":username(request),"coins":request.user.coins,"WABA_ID":display_whatsapp_id(request),"PHONE_ID":display_phonenumber_id(request)})
    else:
        return render(request, "media-file.html",context)
        
def initiate_password_reset(request):
    if request.method == "POST":
        email = request.POST.get("email")
        try:
            user = CustomUser.objects.get(email=email)
            token = default_token_generator.make_token(user)
            send_otp(email)
            return redirect("otp_verification", email=email, token=token)
        except ObjectDoesNotExist:
            return render(
                request,
                "password_reset.html",
                {"error_message": "Email does not exist"},
            )
    return render(request, "password_reset.html")


def verify_otp(request, email, token):
    if request.method == "POST":
        otp = request.POST.get("otp")
        if verify_otp_server(otp):
            return redirect("change_password", email=email, token=token)
        else:
            return render(
                request, "otp_verification.html", {"error_message": "Invalid OTP"}
            )
    return render(request, "otp_verification.html")


def change_password(request, email, token):
    if request.method == "POST":
        new_password = request.POST.get("new_password")
        confirm_new_password = request.POST.get("confirm_new_password")
        if new_password == confirm_new_password:
            try:
                user = CustomUser.objects.get(email=email)
                if default_token_generator.check_token(user, token):
                    user.set_password(new_password)
                    user.save()
                    return redirect("login")
                else:
                    return render(
                        request,
                        "change_password.html",
                        {"error_message": "Invalid or expired token"},
                    )
            except ObjectDoesNotExist:
                return render(
                    request,
                    "change_password.html",
                    {"error_message": "Email does not exist"},
                )
        else:
            return render(
                request,
                "change_password.html",
                {"error_message": "Passwords do not match"},
            )
    return render(request, "change_password.html")


def verify_otp_server(otp):
    verify_otp_url = "http://www.whtsappdealnow.in/email/verify_otp"
    params = {"otp": otp}
    verify_otp_response = requests.post(verify_otp_url, params=params)
    return verify_otp_response.status_code == 200


def send_otp(email):
    otp_url ="http://www.whtsappdealnow.in/email/otp"
    params = {"name": "otp", "email": email}
    otp_response = requests.post(otp_url, params=params)

    if otp_response.status_code == 200:
        print("OTP sent successfully.")
    else:
        return redirect("password_reset.html")

##########testing code #############
from django.shortcuts import render
from django.http import JsonResponse
import requests
import json

def facebook_sdk_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            code = data.get('code')

            # Step 1: Exchange code for access token
            params = {
                'client_id': '1002275394751227',  # Replace with your Facebook App ID
                'client_secret': '2a272b5573130b915db4bccc27caa34f',  # Replace with your Facebook App Secret
                'code': code,
                'redirect_uri': 'https://developers.facebook.com/apps/1002275394751227/'
            }
            response = requests.get('https://graph.facebook.com/v20.0/oauth/access_token', params=params)
            token_data = response.json()

            if 'access_token' not in token_data:
                return JsonResponse({'error': 'Failed to retrieve access token'}, status=400)

            access_token = token_data['access_token']

            # Step 2: Debug the access token
            debug_params = {
                'input_token': access_token,
                'access_token': 'EAAE3ZCQ8LZB48BO9KDbpZCjbM6ZADGoAZANvtahzlAaoRqF24zgwUYsGZCSVpi1IkOhgaGnfCzmh5axAWDrXyomeqmhYUSgofSlIXojlBBCkwguOsFUgeCIaXuUZAsBhMiSTBFwyqZCkFTwGV1n700ef4fe1iZAGqVuBr2x9ZAh8AUz3FxxXIOWfDf6xinJAreZChYwFwZDZD'  # Replace with your Facebook App Access Token
            }
            debug_response = requests.get('https://graph.facebook.com/v20.0/debug_token', params=debug_params)
            debug_data = debug_response.json()

            if 'error' in debug_data:
                return JsonResponse({'error': debug_data['error']['message']}, status=400)

            # Step 3: Subscribe WhatsApp Business Account to an application
            waba_id =data.get('waba_id') # Replace with your WhatsApp Business Account ID
            subscribe_endpoint = f'https://graph.facebook.com/v20.0/{waba_id}/subscribed_apps'
            subscribe_params = {
                'subscribed_fields': 'messages, messaging_postbacks, messaging_optins, messaging_referrals',  # Adjust fields as per your requirements
                'access_token': 'EAAE3ZCQ8LZB48BO9KDbpZCjbM6ZADGoAZANvtahzlAaoRqF24zgwUYsGZCSVpi1IkOhgaGnfCzmh5axAWDrXyomeqmhYUSgofSlIXojlBBCkwguOsFUgeCIaXuUZAsBhMiSTBFwyqZCkFTwGV1n700ef4fe1iZAGqVuBr2x9ZAh8AUz3FxxXIOWfDf6xinJAreZChYwFwZDZD'  # Replace with your Business Integration System Token
            }
            subscribe_response = requests.post(subscribe_endpoint, params=subscribe_params)
            subscribe_data = subscribe_response.json()

            if 'success' in subscribe_data:
                # Retrieve the WABA ID from the session info (example assumes frontend sends WABA ID in JSON)
                waba_id = data.get('waba_id')
                

                
                return JsonResponse({'message': 'WhatsApp Business Account subscribed successfully', 'waba_id': waba_id})
            elif 'error' in subscribe_data:
                return JsonResponse({'error': subscribe_data['error']['message']}, status=400)
            else:
                return JsonResponse({'error': 'Unknown error occurred'}, status=500)

        except json.JSONDecodeError as e:
            return JsonResponse({'error': 'Invalid JSON format in request body'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    elif request.method == 'GET':
        # Return the rendered HTML template for GET requests
        return render(request, 'facebook_sdk.html')

    else:
        # Handle other HTTP methods (shouldn't happen in your case)
        return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def schedules(request):
    if not check_user_permission(request.user, 'can_schedule_tasks'):
        return redirect("access_denide")
    scheduledmessages = ScheduledMessage.objects.filter(current_user=request.user.email)
    context = {
        "coins":request.user.coins,
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
    
# @csrf_exempt
# def save_phone_number(request):
#     if request.method == "POST":
#         try:
#             data = json.loads(request.body)
#             response = data.get('response')
#             if response:
#                 phone_number = response['entry'][0]['changes'][0]['value']['contacts'][0]['wa_id']
#                 reply_text = response['entry'][0]['changes'][0]['value']['messages'][0]['button']['text']
#                 phone_number_id = response['entry'][0]['changes'][0]['value']['metadata']['phone_number_id']
#                 waba_id = response['entry'][0]['id']
#                 emails = CustomUser.objects.filter(
#                     phone_number_id=phone_number_id,
#                     whatsapp_business_account_id=waba_id
#                 ).values_list('email', flat=True)
#                 latest_template = TemplateLinkage.objects.filter(
#                     useremail__in=emails,
#                     button_name=reply_text
#                 ).order_by('-updated_at').first()
#                 latest_user = CustomUser.objects.filter(
#                     phone_number_id=phone_number_id
#                 ).first()
#                 if latest_user and latest_user.register_app:
#                     token = latest_user.register_app.token

#                 linked_template_name = latest_template.linked_template_name
#                 image_id = latest_template.image_id
#                 logging.info(f"image_id {image_id}")
                
#                 try:
#                     # Split the image_id and check the resulting list length
#                     parts = image_id.split("|")
                    
#                     if len(parts) >= 2:
#                         image_id = parts[0]
#                         media_type = parts[1]
#                     else:
#                         raise ValueError("image_id format is incorrect. Expected format: 'id|type'")
                
#                 except Exception as e:
#                     logging.info(f"Error {e}")
#                     image_id = None
#                     media_type = "TEXT"
                
#                 if media_type in ["image/jpeg", "image/png"]:
#                     media_type = "IMAGE"
#                 try:
#                     campaign_list = fetch_templates(waba_id, token)
#                     if campaign_list is None :
#                         campaign_list=[]
#                     template_type = get_template_type(campaign_list, linked_template_name)
#                     if template_type == "FLOW":
#                         flow_id = get_flow_id(campaign_list, linked_template_name)
#                         status_code, _ = send_flow_message_api(token, phone_number_id, linked_template_name, flow_id, "en_US", phone_number)
#                     else:
#                         send_api(str(token), str(phone_number_id), str(linked_template_name), "en", str(media_type), str(image_id), [phone_number], None)
#                     logging.info(f"Next reply message sent successfully. Template: {linked_template_name}, Phone Number: {phone_number}, Media Type: {type(media_type)}, Image ID Type: {type(image_id)}")
#                 except Exception as e:
#                     logging.error(f"Failed to send next reply message {e}")
#                 # You can also save it in your model if needed
#                 return JsonResponse({'status': 'success'}, status=200)
#             else:
#                 return JsonResponse({'status': 'error', 'message': 'Phone number missing'}, status=400)
#         except Exception as e:
#             logging.error(f"Error processing phone number: {e}")
#             return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
#     return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)


@csrf_exempt
def save_phone_number(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            response = data.get('response')
            if response:
                phone_number = response['entry'][0]['changes'][0]['value']['contacts'][0]['wa_id']
                try:
                    reply_text = response['entry'][0]['changes'][0]['value']['messages'][0]['button']['text']
                except (KeyError, IndexError):
                    pass
                try:
                    user_response = response['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
                    logging.info(f"user_response {user_response}")
                except (KeyError, IndexError):
                    pass
                phone_number_id = response['entry'][0]['changes'][0]['value']['metadata']['phone_number_id']
                waba_id = response['entry'][0]['id']
                emails = CustomUser.objects.filter(
                    phone_number_id=phone_number_id,
                    whatsapp_business_account_id=waba_id
                ).values_list('email', flat=True)

                try:
                    latest_template = TemplateLinkage.objects.filter(
                        useremail__in=emails,
                        button_name=reply_text
                    ).order_by('-updated_at').first()
                except Exception as e:
                    logging.info(f"Error: {e}")
                    latest_template = None

                try:
                    filter_message_response = MessageResponse.objects.filter(
                        user_response=user_response,
                        user__in=emails
                    ).first()
                    logging.info(f"message_type: {filter_message_response.message_type}")
                except Exception as e:
                    logging.info(f"Error: {e}")
                    filter_message_response =None

                logging.info(f"filter_message_response {filter_message_response}")
                latest_user = CustomUser.objects.filter(
                        phone_number_id=phone_number_id
                    ).first()
                if latest_user and latest_user.register_app:
                    token = latest_user.register_app.token

                if latest_template:
                    linked_template_name = latest_template.linked_template_name
                    image_id = latest_template.image_id
                    logging.info(f"image_id {image_id}")
                    
                    try:
                        # Split the image_id and check the resulting list length
                        parts = image_id.split("|")
                        
                        if len(parts) >= 2:
                            image_id = parts[0]
                            media_type = parts[1]
                        else:
                            raise ValueError("image_id format is incorrect. Expected format: 'id|type'")
                    
                    except Exception as e:
                        logging.info(f"Error {e}")
                        image_id = None
                        media_type = "TEXT"
                    
                    if media_type in ["image/jpeg", "image/png"]:
                        media_type = "IMAGE"
                    try:
                        campaign_list = fetch_templates(waba_id, token)
                        if campaign_list is None :
                            campaign_list=[]
                        template_type = get_template_type(campaign_list, linked_template_name)
                        if template_type == "FLOW":
                            flow_id = get_flow_id(campaign_list, linked_template_name)
                            status_code, _ = send_flow_message_api(token, phone_number_id, linked_template_name, flow_id, "en_US", [phone_number])
                        else:
                            send_api(str(token), str(phone_number_id), str(linked_template_name), "en", str(media_type), str(image_id), [phone_number], None)
                        logging.info(f"Next reply message sent successfully. Template: {linked_template_name}, Phone Number: {phone_number}, Media Type: {type(media_type)}, Image ID Type: {type(image_id)}")
                    except Exception as e:
                        logging.error(f"Failed to send next reply message {e}")
                elif filter_message_response:
                    message_type = filter_message_response.message_type
                    if message_type == "list_message":
                        response = send_bot_api(token, phone_number_id, phone_number, "list_message", body=filter_message_response.body_message, sections=filter_message_response.sections)
                    elif message_type == "reply_button_message":
                        response = send_bot_api(token, phone_number_id, phone_number, "reply_button_message", body=filter_message_response.body_message, button_data=filter_message_response.buttons)
                    elif message_type == "single_product_message":
                        product_data = {"product_retailer_id": filter_message_response.product_retailer_id}
                        response = send_bot_api(token, phone_number_id, phone_number, "single_product_message", body=filter_message_response.body_message, catalog_id=filter_message_response.catalog_id, product_data=product_data)
                    elif message_type == "multi_product_message":
                        multi_product_section = filter_message_response.product_section
                        catelogue_id = multi_product_section[0].pop("catelogue_id")
                        response = send_bot_api(token, phone_number_id, phone_number, "multi_product_message", body=filter_message_response.body_message, catalog_id=catelogue_id, sections=multi_product_section)
                    elif message_type == "send_my_location":
                        response = send_bot_api(token, phone_number_id, phone_number, "location_message", latitude=filter_message_response.latitude, longitude=filter_message_response.longitude, header=filter_message_response.body_message, body=filter_message_response.body_message)
                    elif message_type == "request_user_location":
                        response = send_bot_api(token, phone_number_id, phone_number, "location_request_message", body=filter_message_response.body_message)
                    elif message_type == "send_text_message":
                        response = send_bot_api(token, phone_number_id, phone_number, "text", body=filter_message_response.body_message)
                    elif message_type == 'link_template':
                        send_api(token, phone_number_id, filter_message_response.template_name, "en", "TEXT", None, [phone_number], None)
                    
                # You can also save it in your model if needed
                return JsonResponse({'status': 'success'}, status=200)
            else:
                return JsonResponse({'status': 'error', 'message': 'Phone number missing'}, status=400)
        except Exception as e:
            logging.error(f"Error processing phone number: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
    

@login_required
def create_flow_message(request):
    token, _ = get_token_and_app_id(request)
    waba_id = display_whatsapp_id(request)
    campaign_list = fetch_templates(display_whatsapp_id(request), token)

    flows = get_flows(token, waba_id)
    local_db_flows = Flows.objects.filter(email=request.user)
    flow_value = list(local_db_flows.values_list('flows', flat=True))
    filtered_flows = [flow for flow in flows if flow['name'] in flow_value]
    
    if campaign_list is None :
        campaign_list=[]

    template_database = Templates.objects.filter(email=request.user)
    template_value = list(template_database.values_list('templates', flat=True))
    templates = [campaign_list[i] for i in range(len(campaign_list)) if campaign_list[i]['template_name'] in template_value]
    if request.method == 'POST':
        # Retrieve form data from POST request
        flow_name = request.POST.get('name')
        category = request.POST.get('category')
        json_flow = request.POST.get('json_flow')

        flow_data = json.loads(json_flow, cls=CustomJSONDecoder)

        try:
            response = create_flow(token, waba_id, flow_name, category, flow_data)
            if response.status_code == 200:
                Flows.objects.create(email=request.user, flows=flow_name)
                messages.success(request, "Flow Created Successfully")
            else:
                messages.error(request, "Failed to create flow template")
        except Exception as e:
            messages.error(request, "Failed to create flow template")
            logging.error(f"Couldn't create flow template {e}")

    context = {
        "flows": filtered_flows,
        "coins": request.user.coins,
        "username": username(request),
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request),
        "campaign_list": templates,
    }

    return render(request, "create_flow_template.html", context)


@login_required
@csrf_exempt
def publish_flow(request, flow_id):
    ACCESS_TOKEN, _ = get_token_and_app_id(request)
    BASE_URL = 'https://graph.facebook.com/v20.0'
    url = f"{BASE_URL}/{flow_id}/publish"
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers)
        
        if response.status_code == 200:
            return JsonResponse({
                'success': True,
                'message': f'Flow "{flow_id}" successfully published'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': f'Failed to publish flow. Status code: {response.status_code}'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error publishing flow: {str(e)}'
        })

@login_required
@csrf_exempt
def deprecate_flow(request, flow_id):
    ACCESS_TOKEN, _ = get_token_and_app_id(request)
    BASE_URL = 'https://graph.facebook.com/v20.0'
    url = f"{BASE_URL}/{flow_id}/deprecate"
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers)
        
        if response.status_code == 200:
            return JsonResponse({
                'success': True,
                'message': f'Flow "{flow_id}" successfully deprecated'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': f'Failed to deprecate flow. Status code: {response.status_code}'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error deprecating flow: {str(e)}'
        })

def create_flow(token, waba_id, flow_name, categories, flow_json):
    BASE_URL = 'https://graph.facebook.com/v20.0'
    url = f"{BASE_URL}/{waba_id}/flows"
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    data = {
        "name": flow_name,
        "categories": categories
    }

    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        flow_id = response.json().get('id')
        response = update_flow_json(BASE_URL, flow_id, flow_name, token, flow_json)
        return response
    else:
        return JsonResponse({
            'success': False,
            'message': f"Failed to create flow. Status code: {response.status_code}, Response: {response.text}"
        })


def update_flow_json(base_url, flow_id, flow_name, access_token, flow_json):
    url = f"{base_url}/{flow_id}/assets"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    
    files = {
        'file': ('flow.json', json.dumps(flow_json), 'application/json'),
        'name': (None, 'flow.json'),
        'asset_type': (None, 'FLOW_JSON')
    }

    response = requests.post(url, headers=headers, files=files)
    
    if response.status_code == 200:
        return response
    else:
        return False

@login_required
@csrf_exempt
def delete_flow(request, flow_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    ACCESS_TOKEN, _ = get_token_and_app_id(request)
    BASE_URL = 'https://graph.facebook.com/v20.0'
    
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}'
    }
    
    try:
        # First, get the flow details to find its name
        flow_details_url = f"{BASE_URL}/{flow_id}"
        flow_response = requests.get(flow_details_url, headers=headers)
        
        if flow_response.status_code != 200:
            return JsonResponse({
                'success': False,
                'message': f'Failed to get flow details. Status code: {flow_response.status_code}'
            })
            
        flow_name = flow_response.json().get('name')
        if not flow_name:
            return JsonResponse({
                'success': False,
                'message': 'Could not find flow name'
            })
        
        # Delete from Facebook
        delete_url = f"{BASE_URL}/{flow_id}"
        response = requests.delete(delete_url, headers=headers)
        
        try:
            flow = Flows.objects.get(email=request.user, flows=flow_name)
            flow.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Flow successfully deleted from Facebook and database'
            })
        except Flows.DoesNotExist:
            return JsonResponse({
                'success': True,
                'message': 'Flow deleted from Facebook but not found in database'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error deleting flow: {str(e)}'
        })


@login_required
def send_flow_message(request):
    if not check_user_permission(request.user, 'can_send_flow_message'):
        return redirect("access_denide")
    phone_id = display_phonenumber_id(request)
    token, _ = get_token_and_app_id(request)
    current_user = request.user
    
    scheduled_messages = ScheduledMessage.objects.filter(schedule_date=now().date())
    scheduled_times = scheduled_messages.values_list('schedule_time', flat=True)
    
    try:
        coins = request.user.coins
        report_list = ReportInfo.objects.filter(email=request.user)
        template_database = Templates.objects.filter(email=request.user)
        template_value = list(template_database.values_list('templates', flat=True))
        # Assuming fetch_templates and display_whatsapp_id are defined elsewhere
        campaign_list = fetch_templates(display_whatsapp_id(request), token)
        if campaign_list is None :
            campaign_list=[]
        templates = [campaign for campaign in campaign_list if campaign['template_name'] in template_value]

        context = {
            "template_name": [template['template_name'] for template in templates],
            "template_data": json.dumps([template['template_data'] for template in templates]),
            "template_status": json.dumps([template['status'] for template in templates]),
            "template_button": json.dumps([json.dumps(template['button']) for template in templates]),
            "template_media": json.dumps([template.get('media_type', 'No media available') for template in templates]),
            "scheduled_times": scheduled_times
        }
    except Exception as e:
        logger.error(f"Error fetching templates: {e}")
        context = {
            "template_name": [],
            "template_data": json.dumps([]),
            "template_status": json.dumps([]),
            "template_button": json.dumps([]),
            "template_media": json.dumps([]),
            "scheduled_times": scheduled_times
        }

    context.update({
        "coins": coins if 'coins' in locals() else None,
        "report_list": report_list,
        "campaign_list": campaign_list,
        "username": request.user.email if request.user.is_authenticated else None,
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request)
    })

    if request.method == 'POST':
        campaign_title = request.POST.get("campaign_title")
        flow_name = request.POST.get("params")
        uploaded_file = request.FILES.get("files", None)
        contacts = request.POST.get("contact_number", "").strip()
        if not campaign_title or not flow_name:
            messages.error(request, "Flow name is required.")
            return render(request, "send-flow.html", context)

        discount = show_discount(request.user)
        all_contact, contact_list = validate_phone_numbers(request,contacts, uploaded_file, discount)

        try:
            send_flow_messages_with_report(current_user, token, phone_id, campaign_list, flow_name, all_contact, contact_list,campaign_title, request)
        except Exception as e:
            logger.error(f"Error processing Flow form: {e}")
            messages.error(request, "There was an error processing your request.")
        return redirect('send_flow_message')
        
    return render(request, "send-flow.html", context)
    
@login_required
def delete_template(request):
    token, app_id = get_token_and_app_id(request)
    template_name = request.POST.get('template_name')
    template_id = request.POST.get('template_id')

    delete_result = delete_whatsapp_template(waba_id=display_whatsapp_id(request), token=token, template_name=template_name, template_id=template_id)
    
    if delete_result:
        print(f"Template '{template_name}' deleted successfully.")
    else:
        print(f"Failed to delete template '{template_name}'.")
    
    return redirect('campaign')
    
@login_required
def link_templates(request):
    if not check_user_permission(request.user, 'can_link_templates'):
        return redirect("access_denide")
    df = download_linked_report(request)
    token, app_id = get_token_and_app_id(request)
    campaign_list = fetch_templates(display_whatsapp_id(request), token)
    if campaign_list is None:
        campaign_list = []

    
    templatelinkage = TemplateLinkage.objects.filter(useremail= request.user)
    button_names = list(templatelinkage.values_list('button_name', flat=True))
    if button_names:
        counts = [int(df['message_body'].str.lower().str.contains(button.lower()).fillna(False).sum()) for button in button_names]
        # Create a list of dictionaries combining templatelinkage and counts
        templatelinkage_with_counts = []
        for linkage, count in zip(templatelinkage, counts):
            linkage_dict = {
                'id': linkage.id,
                'template_name': linkage.template_name,
                'button_name': linkage.button_name,
                'linked_template_name': linkage.linked_template_name,
                'image_id': linkage.image_id,
                'count': count
            }
            templatelinkage_with_counts.append(linkage_dict)
    else:
        templatelinkage_with_counts = []
    
    # templatelinkage = zip(templatelinkage, counts)
    template_database = Templates.objects.filter(email=request.user)
    template_value = list(template_database.values_list('templates', flat=True))
    templates = [campaign for campaign in campaign_list if campaign['template_name'] in template_value]

    context = {
        "coins": request.user.coins,
        "username": username(request),
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request),
        "template_name": [template['template_name'] for template in templates],
        "template_data": json.dumps([template['template_data'] for template in templates]),
        "template_status": json.dumps([template['status'] for template in templates]),
        "template_button": json.dumps([json.dumps(template['button']) for template in templates]),
        "template_media": json.dumps([template.get('media_type', 'No media available') for template in templates]),
        "campaign_list": campaign_list,
        "template_value": template_value,
        "templatelinkage": templatelinkage_with_counts
    }

    if request.method == 'POST':
        template_name = request.POST.get('template_name')
        if not template_name:
            messages.error(request, "Template name is required.")
            return redirect('link_templates')

        header_type = request.POST.get('header_type')
        header_content = request.POST.get('header_content')

        media_ids = []
        for i in range(1, 4):
            quick_reply = request.POST.get(f'quick_reply_{i}')
            linked_temp = request.POST.get(f'linked_temp_{i}')
            file = request.FILES.get(f'file_{i}')

            media_id = None
            media_type = None
            if file:
                try:
                    media_id, media_type = process_media_file(file, display_phonenumber_id(request), token)
                    time.sleep(1.5)
                except Exception as e:
                    messages.error(request, f"Error processing file {i}: {str(e)}")
                    continue

            media_id_str = f"{media_id}|{media_type}" if media_id else None
            media_ids.append(media_id_str)

            if quick_reply and linked_temp:
                try:
                    TemplateLinkage.objects.create(
                        template_name=template_name,
                        linked_template_name=linked_temp,
                        button_name=quick_reply,
                        useremail=request.user.email,
                        image_id=media_id_str or ''
                    )
                except Exception as e:
                    messages.error(request, f"Error creating template linkage: {str(e)}")

        if header_type in ['headerImage', 'headerVideo', 'headerDocument', 'headerAudio']:
            try:
                header_content = header_handle(header_content, token, app_id)
            except Exception as e:
                messages.error(request, f"Error handling header: {str(e)}")

        messages.success(request, "Template linkages created successfully.")
        return redirect('link_templates')

    return render(request, "link_templates.html", context)

@login_required
def delete_template_linkage(request, id):
    linkage = get_object_or_404(TemplateLinkage, id=id, useremail=request.user)
    if request.method == 'POST':
        try:
            linkage.delete()
            messages.success(request, "Successfully Deleted")
        except Exception as e:
            messages.error(request, "Something went wrong, Try again later")
            logging.error(f"Error in deleting linked template  {e}")
        return redirect('link_templates')
        
@login_required
def download_linked_report(request, button_name=None, start_date=None, end_date=None):
    try:
        # Connect to the database
        connection = mysql.connector.connect(
            host="localhost",
            port=3306,
            user="fedqrbtb_wtsdealnow",
            password="Solution@97",
            database="fedqrbtb_report"
        )
        cursor = connection.cursor()
        
        # Base query
        query = "SELECT * FROM webhook_responses"
        query_params = []
        
        # Add date range filter if dates are provided
        if start_date and end_date and start_date != 'null' and end_date != 'null':
            # Convert date strings to Unix timestamps
            start_timestamp = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp())
            end_timestamp = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp()) + (24 * 60 * 60)  # Add 24 hours
            
            query += " WHERE CAST(message_timestamp AS SIGNED) BETWEEN %s AND %s"
            query_params.extend([start_timestamp, end_timestamp])
            logging.info(f"Date range query part: {query}")
            logging.info(f"Date parameters (timestamps): {query_params}")
        
        # Add button_name filter if provided
        if button_name:
            from urllib.parse import unquote
            button_name = unquote(button_name)
            
            if 'WHERE' in query:
                query += " AND LOWER(message_body) LIKE LOWER(%s)"
            else:
                query += " WHERE LOWER(message_body) LIKE LOWER(%s)"
            query_params.append(f"%{button_name}%")
            
        logging.info(f"Final query: {query}")
        logging.info(f"Final parameters: {query_params}")
        
        # Execute query and log the results
        cursor.execute(query, tuple(query_params))
        rows = cursor.fetchall()
        logging.info(f"Number of rows fetched: {len(rows)}")
        
        # Define headers
        headers = ['Date', 'display_phone_number', 'phone_number_id', 'waba_id',
                   'contact_wa_id', 'status', 'message_timestamp', 'error_code',
                   'error_message', 'contact_name', 'message_from', 'message_type',
                   'message_body']
        
        df = pd.DataFrame(rows, columns=headers)
        
        # Log some sample messages for debugging
        if not df.empty:
            logging.info("Sample messages in the data:")
            sample_messages = df['message_body'].head().tolist()
            logging.info(f"Sample messages: {sample_messages}")
            sample_timestamps = df['message_timestamp'].head().tolist()
            logging.info(f"Sample timestamps: {sample_timestamps}")
        
        # Create the HttpResponse object with CSV header
        response = HttpResponse(content_type='text/csv')
        
        # Generate filename with date range if provided
        if button_name:
            if start_date != 'null' and end_date != 'null':
                filename = f"report_{button_name}_{start_date}_to_{end_date}.csv"
            else:
                filename = f"report_{button_name}_complete.csv"
                
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            # Create CSV writer and write data
            writer = csv.writer(response)
            writer.writerow(headers)  # Write headers
            writer.writerows(rows)    # Write all rows
            
            logging.info(f"CSV file created with {len(rows)} rows")
            return response
        else:
            return df
            
    except Exception as e:
        logger.error(f"Error in download_linked_report: {str(e)}")
        logging.error(f"Full error details: {str(e)}")
        messages.error(request, "An error occurred while generating the report.")
        return redirect('reports')
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
            
    
@login_required
def bot_flow(request):
    if not check_user_permission(request.user, 'can_manage_bot_flow'):
        return redirect("access_denide")
    token, app_id = get_token_and_app_id(request)
    campaign_list = fetch_templates(display_whatsapp_id(request), token)
    template_database = Templates.objects.filter(email=request.user)
    template_value = list(template_database.values_list('templates', flat=True))
    if campaign_list is None:
        campaign_list=[]
    templates = [campaign for campaign in campaign_list if campaign['template_name'] in template_value]

    bot_automation = MessageResponse.objects.filter(user=request.user)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_response = data.get('user_response')
            message_type = data.get('message_type')

            if MessageResponse.objects.filter(user=request.user, user_response=user_response).exists():
                return JsonResponse({
                    'status': 'error',
                    'message': 'This response has already been used. Please use a different response.'
                }, status=400)

            response_data = {
                'user_response': user_response,
                'message_type': message_type
            }

            message_response = MessageResponse(
                user=request.user,
                message_type=message_type,
                user_response=user_response,
                body_message=data.get('body_message', '')
            )

            if data.get('sections'):
                message_response.sections = data['sections']

            if data.get('buttons'):
                message_response.buttons = data['buttons']

            if data.get('productSection'):
                message_response.product_section = data['productSection']

            if message_type == 'send_my_location':
                message_response.latitude = data['product_data']['mylatitude']
                message_response.longitude = data['mylongitude']
            elif message_type in ['single_product_message', 'multi_product_message']:
                message_response.product_retailer_id = data.get('product_data', {}).get('product_retailer_id')
                message_response.catalog_id = data.get('catalog_id')
            elif message_type == 'link_template':
                message_response.template_name = data.get('product_data', {}).get('selectedTempale')

            try:
                message_response.save()
                return JsonResponse({
                    'status': 'success',
                    'message': 'Configuration saved successfully',
                    'data': response_data
                })
            except IntegrityError:
                return JsonResponse({
                    'status': 'error',
                    'message': 'This response has already been used. Please use a different response.'
                }, status=400)

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    context = {
        "current_user": request.user,
        "bot_automation": bot_automation,
        "template_names": [template['template_name'] for template in templates],
        "coins": request.user.coins,
        "username": username(request),
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request)
    }
    return render(request, "bot-flow.html", context)
    
def coins_history_list(request):
    template_database = Templates.objects.filter(email=request.user)
    template_value = list(template_database.values_list('templates', flat=True))
    coins_history = CoinsHistory.objects.filter(user=request.user)
    context = {
            "template_names": template_value,
            "coins": request.user.coins,
            "username": username(request),
            "WABA_ID": display_whatsapp_id(request),
            "PHONE_ID": display_phonenumber_id(request),
            "coins_history":coins_history
            }
    
    return render(request, 'coins_history_list.html', context)
    
def get_preview_url(request, flow_id):
    # Define the URL
    BASE_URL = 'https://graph.facebook.com/v20.0'
    token, _ = get_token_and_app_id(request)
    ACCESS_TOKEN = token
    url = f"{BASE_URL}/{flow_id}?fields=preview.invalidate(false)"

    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}'
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        print("Request successful!")
        data = response.json()
        return data['preview']['preview_url']
    else:
        print(f"Request failed. Status code: {response.status_code}")
        print(response.text)
        return None

def get_preview_url_view(request, flow_id):
    preview_url = get_preview_url(request, flow_id)
    if preview_url:
        return JsonResponse({'preview_url': preview_url})
    else:
        return JsonResponse({'error': 'Failed to fetch preview URL'}, status=400)
        
@csrf_exempt
def create_template_from_flow(request):
    token, _ = get_token_and_app_id(request)
    waba_id = display_whatsapp_id(request)
    if request.method == 'POST':
        flow_id = request.POST.get('flow_id')
        template_name = request.POST.get('template_name')
        category = request.POST.get('category')
        body_text = request.POST.get('body_text')
        lang = request.POST.get('lang')

        response = create_message_template_with_flow(
            waba_id, body_text, lang, category, token, template_name, flow_id
        )
        
        if response:
            messages.success(request, "Flow Template created successfully")
            try:
                Templates.objects.create(email=request.user, templates=template_name)
            except Exception as e:
                logging.error(f"Error, {e}")
            return JsonResponse({'success': True})
        
        else:
            print("response", response)
            messages.error(request, "Failed to crate Flow Template")
            return JsonResponse({'success': False, 'error': 'Failed to create template'})
        
def customuser_list_view(request):
    users = CustomUser.objects.all().values('email', 'username', 'phone_number_id', 'whatsapp_business_account_id',
                                            'coins', 'discount', 'is_active', 'is_staff', 'user_id', 'api_token',
                                            'register_app__app_id', 'register_app__token')
    return JsonResponse(list(users), safe=False)
    
def customuser_detail_view(request, email):
    user = get_object_or_404(CustomUser, email=email)
    user_data = {
        'email': user.email,
        'username': user.username,
        'phone_number_id': user.phone_number_id,
        'whatsapp_business_account_id': user.whatsapp_business_account_id,
        'coins': user.coins,
        'discount': user.discount,
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'user_id': user.user_id,
        'api_token': user.api_token,
        'register_app': {
            'app_id': user.register_app.app_id if user.register_app else None,
            'token': user.register_app.token if user.register_app else None
        }
    }
    return JsonResponse(user_data)
    
    
class UpdateBalanceReportView(APIView):

    def post(self, request):
        try:
            user_id = request.data.get('user_id')
            api_token = request.data.get('api_token')
            coins = request.data.get('coins')
            phone_numbers = request.data.get('phone_numbers')
            all_contact = request.data.get('all_contact')
            template_name = request.data.get('template_name')

            user_data = customuser_list_view(request)

            if isinstance(user_data, JsonResponse):
                data = json.loads(user_data.content.decode('utf-8'))
                filtered_user = next((user for user in data if user['user_id'] == user_id and user['api_token'] == api_token), None)
                
                if filtered_user:
                    user_email = filtered_user['email']
                    logging.info(f"User email: {user_email}")

                    try:
                        schedule_subtract_coins(user_email, coins)
                    except Exception as e:
                        logging.error(f"Error subtracting coins: {str(e)}")
                        return Response({"error": "Failed to subtract coins", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                    try:
                        report_id = create_report(user_email, phone_numbers, all_contact, template_name)
                        return Response({"report_id": report_id}, status=status.HTTP_200_OK)
                    except Exception as e:
                        logging.error(f"Error creating report: {str(e)}")
                        return Response({"error": "Failed to create report", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                else:
                    logging.warning("User not found or invalid API token")
                    return Response({"error": "Invalid user or API token"}, status=status.HTTP_404_NOT_FOUND)
            else:
                logging.error("Unexpected response format from customuser_list_view")
                return Response({"error": "Invalid response format"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except KeyError as e:
            logging.error(f"Missing required field: {str(e)}")
            return Response({"error": f"Missing required field: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return Response({"error": "An unexpected error occurred", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            
class GetReportAPI(APIView):

    def post(self, request):
        try:
            # Extract request data
            user_id = request.data.get('user_id')
            api_token = request.data.get('api_token')
            report_id = request.data.get('report_id')

            # Verify user
            user_data = customuser_list_view(request)
            if isinstance(user_data, JsonResponse):
                data = json.loads(user_data.content.decode('utf-8'))
                filtered_user = next((user for user in data if user['user_id'] == user_id and user['api_token'] == api_token), None)
                
                if not filtered_user:
                    return Response({"error": " 510, Invalid user or API token"}, status=status.HTTP_404_NOT_FOUND)
                
                phone_id = filtered_user['phone_number_id']
            else:
                return Response({"error": "550, Failed to fetch user data"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Fetch report data
            try:
                filtered_reports = ReportInfo.objects.get(campaign_title=report_id)
                contacts = filtered_reports.contact_list.split('\r\n')
                contact_all = [phone.strip() for contact in contacts for phone in contact.split(',')]
            except ReportInfo.DoesNotExist:
                return Response({"error": "560, Report not found"}, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                logging.error(f"Error fetching report: {str(e)}")
                return Response({"error": "570, Failed to get report data"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Database connection setup
            try:
                connection = mysql.connector.connect(
                    host="localhost",
                    port=3306,
                    user="fedqrbtb_wtsdealnow",
                    password="Solution@97",
                    database="fedqrbtb_report"
                )
                cursor = connection.cursor()
                query = "SELECT * FROM webhook_responses"
                cursor.execute(query)
                rows = cursor.fetchall()
            except mysql.connector.Error as err:
                logging.error(f"MySQL Error: {str(err)}")
                return Response({"error": "600, Database connection error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Processing rows into a dictionary for easy lookup
            rows_dict = {(row[2], row[4]): row for row in rows}
            matched_rows = []
            non_reply_rows = [row for row in rows if row[5] != "reply" and row[2] == phone_id]

            # Match contacts and generate report data
            for phone in contact_all:
                matched = False
                row = rows_dict.get((phone_id, phone), None)
                if row:
                    matched_rows.append(row)
                    matched = True
                if not matched and non_reply_rows:
                    # Use a random non-reply row for unmatched contacts
                    new_row = copy.deepcopy(random.choice(non_reply_rows))
                    new_row_list = list(new_row)
                    new_row_list[4] = phone  # Update the phone number in the new row
                    matched_rows.append(tuple(new_row_list))

            cursor.close()
            connection.close()

            # Define header for DataFrame
            header = [
                "Date", "display_phone_number", "phone_number_id", "waba_id", "contact_wa_id",
                "status", "message_timestamp", "error_code", "error_message", "contact_name",
                "message_from", "message_type", "message_body"
            ]

            # Convert matched rows to a pandas DataFrame
            df = pd.DataFrame(matched_rows, columns=header)

            # Optionally, return as a downloadable CSV, or return as JSON (you can adapt this as needed)
            report_data = df.to_dict(orient='records')  # Converts DataFrame to list of dicts

            return Response({"report_data": report_data}, status=status.HTTP_200_OK)

        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return Response({"error": "999, An unexpected error occurred", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def api_manual(request):

    context = {
        "coins": request.user.coins,
        "username": username(request),
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request)
        }
    return render(request, "api_manual.html", context)