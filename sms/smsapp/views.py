# import requests # type: ignore
from django.shortcuts import render, redirect, HttpResponse
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import authenticate, login
from django.core.exceptions import ObjectDoesNotExist
from .models import CustomUser
from django.conf import settings
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required
from .forms import UserLoginForm
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .campaignmail import send_email_change_notification
import logging
from .models import ReportInfo,CampaignData,ReportFile
from django.contrib.auth import logout
import requests
logger = logging.getLogger(__name__)
from datetime import datetime
from django.db.models import Sum
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def user_login(request):
    from .forms import UserLoginForm  # Assuming form is in the same app

    if request.method == "POST":
        form = UserLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]
            user = authenticate(request, email=email, password=password)

            if user:
                login(request, user)
                logger.info(f"User {email} logged in successfully.")
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

@login_required
def username(request):
    username=request.user
    return username

@login_required
def logout_view(request):
    logout(request)
    return redirect("login")

@login_required
def user_dashboard(request):
    coins= request.user.coins
    return render(request, "dashboard.html",{"username":username(request),"coins":coins})
##################
@login_required
def Send_Sms(request):
    if not request.user.is_authenticated:
        return redirect("login")

    ip_address = request.META.get("REMOTE_ADDR", "Unknown IP")
    user = request.user
    coins = user.coins
    report_list = ReportInfo.objects.filter(email=user)
    campaign_list = CampaignData.objects.filter(email=user)

  

    def get_context(extra_context=None):
        context = {
            "ip_address": ip_address,
            "username": username(request),
            "coins": coins,
            "report_list": report_list,
            "campaign_list": campaign_list
        }
        if extra_context:
            context.update(extra_context)
        return context

    if request.method == "POST":
        campaign_title = request.POST.get("campaign_title", "").strip()
        template_id = request.POST.get("params", "").strip()
        media_id = request.POST.get("media_id", "").strip()
        uploaded_file = request.FILES.get("files")
        contacts = request.POST.get("contact_number", "").strip()

        if not campaign_title or not template_id :
            logger.error("Missing required POST parameters.")
            return render(request, "send-sms.html", get_context())

        discount = show_discount(user)
        final_count, contact_list = validate_phone_numbers(contacts, uploaded_file, discount)
    
        try:
            url = "http://www.whtsappdealnow.in/whatsapp/send_messages/"
            params = {"template_id": template_id, "media_id": media_id}
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            requests.post(url, params=params, headers=headers, json=contact_list)
            

            subtract_coins(request, final_count)
            new_message_info = ReportInfo(
                email=user,
                campaign_title=campaign_title,
                message_date=timezone.now(),
                message_delivery=final_count,
                message_send=final_count,
                message_failed=2,  # This should ideally be dynamically set based on actual failures
            )
            new_message_info.save()
            return redirect('send-sms')

        except requests.RequestException as e:
            logger.error(f"Error sending SMS: {e}")
            return render(request, "send-sms.html", get_context())

    return render(request, "send-sms.html", get_context())
#Valid _and _ Duplicate method
import re
def validate_phone_numbers(contacts, uploaded_file,discount):
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
    import openpyxl        
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
    from django.http import request
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
    discountnumber=fnn(valid_numbers,discount)

    final_list=whitelist(valid_numbers,whitelist_number,blacklist_number,discountnumber)
    
    
    return len(valid_numbers), final_list

from django.contrib import messages

def show_discount(user):
    discount = user.discount
    return discount

@login_required
def subtract_coins(request, final_count):
    user = request.user
    if user is None or user.coins is None:
        messages.error(request, "User or user coins not found.")
        return
    final_coins = final_count
    if user.coins >= final_coins: 
        user.coins -= final_coins
        user.save()
        messages.success(request, f"Message Send Successfully and Deduct {final_coins} coins from your account.")
    else:
        messages.error(request, "You don't have enough coins to proceed.")

@login_required
def Campaign(request):
    
    campaign_list = CampaignData.objects.filter(email=request.user)

    if request.method == 'POST':
        template_id = request.POST.get('template_id')
        sub_service = request.POST.get('sub_service')
        media_type=request.POST.get('media_type')
        template_data = request.POST.get('template_data')
        action_type = request.POST.get('actionType')
        button_name = request.POST.get('buttonName')
        print(button_name)
        contact_number = request.POST.get('contactNumber')
        website_url = request.POST.get('websiteUrl')


        try:
            # Attempt to create a new campaign
            CampaignData.objects.create(
                email=request.user,
                template_id=template_id,
                sub_service=sub_service,
                media_type=media_type,
                template_data=template_data,
                action_type=action_type,
                button_name=button_name,
                contact_number=contact_number,
                website_url=website_url,

            )
            send_email_change_notification(request.user, template_id)
            return render(request, "Campaign.html", {"campaign_list": campaign_list})
        except IntegrityError as e:
            # If the template_id already exists, return the existing campaign list
                    
            campaign_list = CampaignData.objects.filter(email=request.user)
            return render(request, "Campaign.html", {"campaign_list": campaign_list})



    return render(request, "Campaign.html", {"campaign_list": campaign_list,"username":username(request)})

@login_required
def delete_campaign(request, template_id):
    if template_id is None:
        return 
    campaign_data = get_object_or_404(CampaignData, template_id=template_id)
    campaign_data.delete()
    return redirect('campaign')

@login_required
def Reports(request):
    report_list = ReportInfo.objects.filter(email=request.user)
    file_list = ReportFile.objects.filter(email=request.user)
    
    # Create a dictionary to map report ids to their corresponding files
    file_map = {file.report_id: file for file in file_list}
    
    # Annotate each report with its corresponding file
    for report in report_list:
        report.file = file_map.get(report.id)
    
    return render(request, 'reports.html', {
        "report_list": report_list,
        "username":username(request)
                })

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
@login_required
def download_pdf(request, report_id):
    report = get_object_or_404(ReportInfo, pk=report_id)
    if report.email != request.user:
        return HttpResponse("You don't have permission to download this PDF.", status=403)
    with open(report.report_file.path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{report.report_file.name}"'
        return response


from .models import Whitelist_Blacklist

def whitelist_blacklist(request):
    # Fetch all objects from the Whitelist_Blacklist model
    whitelist_blacklists = Whitelist_Blacklist.objects.all()
    whitelist_phones = [obj.whitelist_phone for obj in whitelist_blacklists]
    whitelist_phones_cleaned = [phone for sublist in whitelist_phones for phone in sublist.split('\r\n')]
    

    blacklist_phones = [obj.blacklist_phone for obj in whitelist_blacklists]
    blacklist_phones_cleaned = [phone for sublist in blacklist_phones for phone in sublist.split('\r\n')]
    
    return whitelist_phones_cleaned ,blacklist_phones_cleaned


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests

def get_media_format(file_extension):
    media_formats = {
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
        'gif': 'image/gif', 'bmp': 'image/bmp', 'svg': 'image/svg+xml',
        'mp4': 'video/mp4', 'avi': 'video/x-msvideo', 'mov': 'video/quicktime',
        'flv': 'video/x-flv', 'mkv': 'video/x-matroska', 'mp3': 'audio/mpeg',
        'aac': 'audio/aac', 'ogg': 'audio/ogg', 'wav': 'audio/wav',
        'pdf': 'application/pdf', 'doc': 'application/msword', 'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'ppt': 'application/vnd.ms-powerpoint', 'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'xls': 'application/vnd.ms-excel', 'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'txt': 'text/plain', 'csv': 'text/csv'
    }
    return media_formats.get(file_extension.lower(), 'application/octet-stream')

def generate_id(template_id, media_type, file):
    url = "https://automate.nexgplatforms.com/api/v1/wa/upload"
    headers = {
        "Authorization": "cTlQLW44Mi05aFF1UEoxUmw3VGp5MGlxRFpqWkdXRXRTVHViUUk3d3VrSTo=",
        "accept": "application/json",
    }
    data = {
        "templateid": template_id,
        "serviceType": "transactional"
    }
    files = [
       ('file', (file.name, file.file, media_type))
    ]
    response = requests.post(url=url, headers=headers, data=data, files=files)
    return response.json()
@login_required
@csrf_exempt
def upload_media(request):
    if request.method == 'POST':
        template_id = request.POST.get('template_id')
        file = request.FILES['file']
        file_extension = file.name.split('.')[-1]
        media_type = get_media_format(file_extension)
        response = generate_id(template_id, media_type, file)
       
        return render(request, "media-file.html", {'response': response.get('data', {}).get('media_transaction_key'),"username":username(request)})
    else:
        return render(request, "media-file.html",{"username":username(request)})
        


# Password Reset Method
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

