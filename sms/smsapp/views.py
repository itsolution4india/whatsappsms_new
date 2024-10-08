
from django.shortcuts import render, redirect, HttpResponse
from django.http import HttpResponse
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import authenticate, login
from django.core.exceptions import ObjectDoesNotExist
from .models import CustomUser, RegisterApp, ScheduledMessage, TemplateLinkage
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
from .models import ReportInfo,Templates
from django.contrib.auth import logout
from django.utils import timezone
import requests
logger = logging.getLogger(__name__)
from datetime import datetime
from django.db.models import Sum
from django.views.decorators.csrf import csrf_exempt
from .display_templates import fetch_templates
from .media_id import get_media_format,generate_id
from .send_message import send_messages_api
from .create_template import template_create
# from .message_id import generate_pattern
import openpyxl 
from .models import Whitelist_Blacklist
from django.contrib import messages
from django.http import request
from django.http import FileResponse, Http404
import os
from django.conf import settings 
from .forms import UserLoginForm  
import json
import ast
import random
from .campaign_media_id import header_handle
#from .smsapi import send_api
from .fastapidata import send_api
from django.utils.timezone import now

from .functions.send_messages import send_messages, display_phonenumber_id, save_schedule_messages
from .utils import check_schedule_timings
@csrf_exempt

def user_login(request):
    
    if request.method == "POST":
        form = UserLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]
            user = authenticate(request, email=email, password=password)

            if user:
                login(request, user)
                logger.info(f"{now().date()}: User {email} logged in successfully.")
                return redirect("dashboard")
            else:
                # Authentication failed
                logger.warning(f"Failed login attempt for email: {email}")
                form.add_error(None, "Invalid email or password.")
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
            if not request.user.is_authenticated:
                
                messages.error(request, "User is not authenticated.")
                return render(request, "send-sms.html", context)

            campaign_title = request.POST.get("campaign_title")
            template_name = request.POST.get("params")
            media_file = request.FILES['file']
            file_extension = media_file.name.split('.')[-1]
            media_type = get_media_format(file_extension)
            media_id = generate_id(display_phonenumber_id(request), media_type, media_file, token) 
            media_id = media_id['id']
            media_id = request.POST.get("media_id")
            uploaded_file = request.FILES.get("files", None)
            contacts = request.POST.get("contact_number", "").strip()

            action_type = request.POST.get("action_type")

            if not campaign_title or not template_name:
                messages.error(request, "Campaign title and template name are required.")
                return render(request, "send-sms.html", context)
         
            discount = show_discount(request.user)
            all_contact, contact_list = validate_phone_numbers(request,contacts, uploaded_file, discount)
            
            #generate_pattern(template_name, all_contact, contact_list)
            if action_type == "submit":
                send_messages(current_user, token, display_phonenumber_id(request), campaign_list, template_name, media_id, all_contact, contact_list, campaign_title, request)
            else:
                schedule_date = request.POST.get("schedule_date")
                schedule_time = request.POST.get("schedule_time")
                result = check_schedule_timings(schedule_time)
                if result:
                    messages.warning(request, f"The time {schedule_time}, is busy. Please choose from these available options: {result}")
                else:
                    messages.success(request, "Message Scheduled Successfully")
                    save_schedule_messages(current_user, template_name, media_id, all_contact, contact_list, campaign_title, schedule_date, schedule_time)
                    
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

    final_list=whitelist(valid_numbers,whitelist_number,blacklist_number,discountnumber)
    

    return valid_numbers, final_list

####################
@login_required
def Campaign(request):
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
        if header_type in ['headerImage','headerVideo','headerDocument','headerAudio']:
            header_content = header_handle(header_content, token, app_id)
        
        if quick_reply_one and linked_temp_one:
            TemplateLinkage.objects.create(template_name=template_name, linked_template_name=linked_temp_one, button_name=quick_reply_one, useremail=request.user.email)

        if quick_reply_two and linked_temp_two:
            TemplateLinkage.objects.create(template_name=template_name, linked_template_name=linked_temp_two, button_name=quick_reply_two, useremail=request.user.email)

        if quick_reply_three and linked_temp_three:
            TemplateLinkage.objects.create(template_name=template_name, linked_template_name=linked_temp_three, button_name=quick_reply_three, useremail=request.user.email)
            
        try:
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
                quick_reply_three=quick_reply_three
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

        # Generate CSV as HttpResponse (stream the file)
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
    
@csrf_exempt
def save_phone_number(request):    
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            response = data.get('response')
            if response:
                phone_number = response['entry'][0]['changes'][0]['value']['contacts'][0]['wa_id']
                reply_text = response['entry'][0]['changes'][0]['value']['messages'][0]['button']['text']
                phone_number_id = response['entry'][0]['changes'][0]['value']['metadata']['phone_number_id']
                waba_id = response['entry'][0]['id']
                emails = CustomUser.objects.filter(
                    phone_number_id=phone_number_id,
                    whatsapp_business_account_id=waba_id
                ).values_list('email', flat=True)
                latest_template = TemplateLinkage.objects.filter(
                    useremail__in=emails,
                    button_name=reply_text
                ).order_by('-updated_at').first()
                latest_user = CustomUser.objects.filter(
                    phone_number_id=phone_number_id
                ).first()
                if latest_user and latest_user.register_app:
                    token = latest_user.register_app.token

                linked_template_name = latest_template.linked_template_name

                try:
                    logging.info(f"Next message details: {token, phone_number_id, linked_template_name, "en", "TEXT", None, [phone_number]}")
                    logging.info(f"Next message details: {type(token), type(phone_number_id), type(linked_template_name), type("en"), type("TEXT"), None, type([phone_number])}")
                    send_api(token, phone_number_id, linked_template_name, "en", 'TEXT', None, [phone_number])
                    logging.info(f"Next reply message send successfully {linked_template_name}, {phone_number}")
                except Exception as e:
                    logging.error(f"Failed to send next reply message {e}")
                # You can also save it in your model if needed
                return JsonResponse({'status': 'success'}, status=200)
            else:
                return JsonResponse({'status': 'error', 'message': 'Phone number missing'}, status=400)
        except Exception as e:
            logging.error(f"Error processing phone number: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)