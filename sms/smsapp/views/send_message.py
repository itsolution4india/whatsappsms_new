from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from ..models import ReportInfo,Templates, ScheduledMessage, CountryPermission, Whitelist_Blacklist, Group, Contact
from ..media_id import get_media_format,generate_id
from django.contrib import messages
import json, re, openpyxl
from ..functions.template_msg import fetch_templates
from django.utils.timezone import now
from ..functions.send_messages import send_messages, display_phonenumber_id, save_schedule_messages
from ..utils import check_schedule_timings, validate_balance, get_token_and_app_id, display_whatsapp_id, logger, show_discount, make_variables_list, get_template_details
from .auth import check_user_permission
from ..functions.flows import send_flow_messages_with_report, send_carousel_messages_with_report
from .reports import get_latest_rows_by_contacts, get_unique_phone_numbers
from ..fastapidata import send_validate_req, send_carousel_message_api
import pandas as pd
from ..media_id import process_media_file
import time


@login_required
def Send_Sms(request):
    if not check_user_permission(request.user, 'can_send_sms'):
        return redirect("access_denide")
    ip_address = request.META.get("REMOTE_ADDR", "Unknown IP")
    token, _ = get_token_and_app_id(request)
    current_user = request.user
    
    scheduled_messages = ScheduledMessage.objects.filter(schedule_date=now().date())
    scheduled_times = scheduled_messages.values_list('schedule_time', flat=True)
    
    groups = Group.objects.all()
    
    try:
        report_list = ReportInfo.objects.filter(email=request.user)
        template_database = Templates.objects.filter(email=request.user)
        template_value = list(template_database.values_list('templates', flat=True))
        
        campaign_list = fetch_templates(display_whatsapp_id(request), token, None, False)
        if campaign_list is None :
            campaign_list=[]
        templates = [campaign for campaign in campaign_list if campaign['template_name'] in template_value]

        context = {
            "template_name": [template['template_name'] for template in templates],
            "template_data": json.dumps([template['template_data'] for template in templates]),
            "template_status": json.dumps([template['status'] for template in templates]),
            "template_images": json.dumps([template['media_link'] for template in templates]),
            "template_images_one": json.dumps([template['image_one'] for template in templates]),
            "template_images_two": json.dumps([template['image_two'] for template in templates]),
            "template_images_three": json.dumps([template['image_three'] for template in templates]),
            "template_button": json.dumps([json.dumps(template['button']) for template in templates]),
            "template_media": json.dumps([template.get('media_type', 'No media available') for template in templates]),
            "scheduled_times": scheduled_times,
            "groups":groups
        }
    except Exception as e:
        logger.error(f"Error fetching templates: {e}")
        context = {
            "template_name": [],
            "template_data": json.dumps([]),
            "template_status": json.dumps([]),
            "template_button": json.dumps([]),
            "template_media": json.dumps([]),
            "template_images": json.dumps([]),
            "template_images_one": json.dumps([]),
            "template_images_two": json.dumps([]),
            "template_images_three": json.dumps([]),
            "scheduled_times": scheduled_times
        }

    context.update({
        "ip_address": ip_address,
        "coins":request.user.marketing_coins + request.user.authentication_coins,
        "marketing_coins":request.user.marketing_coins,
        "authentication_coins":request.user.authentication_coins,
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
            selectedGroup = request.POST.get("selectedGroup", None)
            add_91 = request.POST.get("add_91")
            for key in request.POST:
                if key.startswith('variable'):
                    submitted_variables.append(request.POST[key]) if request.POST[key] else None
                    
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

            if selectedGroup and selectedGroup != 'nan':
                group = Group.objects.get(name=selectedGroup)
                available_contacts = Contact.objects.filter(groups=group) if group else Contact.objects.all()
                contact_list = [contact.phone_number for contact in available_contacts]
            else:
                contact_list = None
            numbers_list = set()
            
            contacts = contact_list if contact_list and not contacts else contacts
            if contacts:
                try:
                    numbers_list.update(contacts.split("\r\n"))
                except:
                    numbers_list = contacts
            
            if (not campaign_title or not template_name) and action_type == "submit":
                messages.error(request, "Campaign title and template name are required.")
                return redirect('send-sms')
         
            discount = show_discount(request.user)
            all_contact, contact_list, invalid_numbers, csv_variables = validate_phone_numbers(request,contacts, uploaded_file, discount, add_91)
            if not contact_list:
                messages.error(request, "Number validation failed. Include the country code.")
                return redirect('send-sms')
            try:
                detailes = get_template_details(campaign_list, template_name)
                category = detailes['category']
            except Exception as e:
                category = None
                logger.error(f"Failed get template category {str(e)}")
                
            coin_validation = validate_balance(request, len(all_contact), category)
            if not coin_validation:
                messages.error(request, "Insufficient balance. Recharge to continue our services.")
                return redirect('send-sms')
            if action_type == "submit":
                send_messages(current_user, token, display_phonenumber_id(request), campaign_list, template_name, media_id, all_contact, contact_list, campaign_title, request, submitted_variables, csv_variables)
            elif action_type == 'validateRequest':
                if invalid_numbers:
                    _ = send_validate_req(token, display_phonenumber_id(request), invalid_numbers, " ")
                    
                    validation_data = get_latest_rows_by_contacts(invalid_numbers)
                    validation_data = validation_data[validation_data['error_code'] == 131026]
                    final_invalid_numbers = validation_data['contact_wa_id'].to_list()
                    final_valid_numbers = [item for item in list(numbers_list) if item not in final_invalid_numbers]
                    
                    logger.info(f"db output {final_invalid_numbers} {final_valid_numbers}")
                    context.update({
                        "final_invalid_numbers": ', '.join(str(num) for num in final_invalid_numbers),
                        "final_valid_numbers": ', '.join(str(num) for num in final_valid_numbers)
                        })
                    logger.info(f"Context being passed to template: {context}")
                    return render(request, "send-sms.html", context)
                else:
                    logger.info("No any invalid numbers")
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

def process_phone_numbers(numbers_list, db_phonenumbers, patterns):
    valid_numbers = set()
    invalid_numbers = set()
    
    for phone_number in numbers_list:
        phone_number = phone_number.strip()
        if phone_number not in db_phonenumbers:
            invalid_numbers.add(phone_number)
        for _, pattern in patterns.items():
            if pattern.match(phone_number):
                valid_numbers.add(phone_number)
                break
        else:
            invalid_numbers.add(phone_number)
    
    return valid_numbers, invalid_numbers

def validate_phone_numbers(request, contacts, uploaded_file, discount, add_91=None):
    valid_numbers = set()
    invalid_numbers = set()
    csv_variables = None
    
    # Get user's country permissions
    try:
        permissions = CountryPermission.objects.get(user=request.user)
    except CountryPermission.DoesNotExist:
        permissions = None

    # Define country-specific patterns
    patterns = {}
    if permissions:
        if permissions.can_send_msg_to_india:
            patterns['india'] = re.compile(r"^\+?91\d{10}$")
        if permissions.can_send_msg_to_nepal:
            patterns['nepal'] = re.compile(r"^\+?977\d{9}$")
        if permissions.can_send_msg_to_us:
            patterns['us'] = re.compile(r"^\+?1\d{10}$")
        if permissions.can_send_msg_to_australia:
            patterns['australia'] = re.compile(r"^\+?61\d{9}$")
        if permissions.can_send_msg_to_uae:
            patterns['uae'] = re.compile(r"^\+?971\d{9}$")

    # If no permissions are set, return empty lists
    if not patterns:
        return [], []

    # Parse contacts from POST request
    numbers_list = set()
    if contacts or contacts != '':
        try:
            numbers_list.update(contacts.split("\r\n"))
        except:
            numbers_list = contacts

    # Parse contacts from uploaded file
    db_phonenumbers = get_unique_phone_numbers()
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        if add_91:
            df['phone_numbers'] = df['phone_numbers'].astype(str)
            df['phone_numbers'] = df['phone_numbers'].apply(lambda x: '91' + x if not x.startswith('91') else x)
        for number in df['phone_numbers']:
            numbers_list.add(str(number))
        valid_numbers, invalid_numbers = process_phone_numbers(numbers_list, db_phonenumbers, patterns)
        csv_variables = make_variables_list(df, valid_numbers)
    
    # Validate phone numbers against permitted country patterns
    if not uploaded_file:
        valid_numbers, invalid_numbers = process_phone_numbers(numbers_list, db_phonenumbers, patterns)

    # Get whitelist and blacklist numbers
    whitelist_number, blacklist_number = whitelist_blacklist(request)

    def fnn(valid_numbers, discount):
        return (len(valid_numbers) * discount) // 100

    def whitelist(valid_numbers, whitelist_number, blacklist_numbers, discount):
        final_list = []
        
        # Add whitelisted numbers that aren't blacklisted
        for num in valid_numbers:
            if num in whitelist_number and num not in blacklist_numbers:
                final_list.append(num)
        
        # Add non-whitelisted, non-blacklisted numbers after discount
        count = 0
        for num in valid_numbers:
            if num not in whitelist_number and num not in blacklist_numbers:
                count += 1
                if count > discount:
                    final_list.append(num)
        
        return final_list

    valid_numbers = list(valid_numbers)
    if len(valid_numbers) > 100:
        discount = discount
    else:
        discount = 0
        phone_numbers_string = ",".join(valid_numbers)
        Whitelist_Blacklist.objects.create(
            email=request.user,
            whitelist_phone=phone_numbers_string
        )

    discountnumber = fnn(valid_numbers, discount)
    
    final_list = whitelist(valid_numbers, whitelist_number, blacklist_number, discountnumber)
    
    if uploaded_file:
        csv_variables = [record for record in csv_variables if record[0] in [num for num in final_list]]
    
    return valid_numbers, final_list, list(set(invalid_numbers)), csv_variables

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
        campaign_list = fetch_templates(display_whatsapp_id(request), token, None, False)
        if campaign_list is None :
            campaign_list=[]
        templates = [campaign for campaign in campaign_list if campaign['template_name'] in template_value]

        context = {
            "template_name": [template['template_name'] for template in templates],
            "template_data": json.dumps([template['template_data'] for template in templates]),
            "template_status": json.dumps([template['status'] for template in templates]),
            "template_button": json.dumps([json.dumps(template['button']) for template in templates]),
            "template_media": json.dumps([template.get('media_type', 'No media available') for template in templates]),
            "template_images": json.dumps([template['media_link'] for template in templates]),
            "template_images_one": json.dumps([template['image_one'] for template in templates]),
            "template_images_two": json.dumps([template['image_two'] for template in templates]),
            "template_images_three": json.dumps([template['image_three'] for template in templates]),
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
        "coins":request.user.marketing_coins + request.user.authentication_coins,
        "marketing_coins":request.user.marketing_coins,
        "authentication_coins":request.user.authentication_coins,
        "report_list": report_list,
        "campaign_list": campaign_list,
        "username": request.user.email if request.user.is_authenticated else None,
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request)
    })

    if request.method == 'POST':
        campaign_title = request.POST.get("campaign_title")
        flow_name = request.POST.get("params")
        add_91 = request.POST.get("add_91")
        uploaded_file = request.FILES.get("files", None)
        contacts = request.POST.get("contact_number", "").strip()
        if not campaign_title or not flow_name:
            messages.error(request, "Flow name is required.")
            return render(request, "send-flow.html", context)

        discount = show_discount(request.user)
        all_contact, contact_list, _, _ = validate_phone_numbers(request,contacts, uploaded_file, discount, add_91)
        
        try:
            detailes = get_template_details(campaign_list, flow_name)
            category = detailes['category']
        except Exception as e:
            category = None
            logger.error(f"Failed get template category {str(e)}")
            
        coin_validation = validate_balance(request, len(all_contact), category)
        if not coin_validation:
            messages.error(request, "Insufficient balance. Recharge to continue our services.")
            return render(request, "send-flow.html", context)
        logger.info(f"Send_Flow: {current_user}, {phone_id}, {campaign_list}, {flow_name}, {all_contact}, {contact_list}, {campaign_title}")
        try:
            send_flow_messages_with_report(current_user, token, phone_id, campaign_list, flow_name, all_contact, contact_list,campaign_title, request)
        except Exception as e:
            logger.error(f"Error processing Flow form: {e}")
            messages.error(request, "There was an error processing your request.")
        return redirect('send_flow_message')
        
    return render(request, "send-flow.html", context)


@login_required
def send_carousel_messages(request):
    phone_id = display_phonenumber_id(request)
    token, _ = get_token_and_app_id(request)
    current_user = request.user
    
    try:
        report_list = ReportInfo.objects.filter(email=request.user)
        template_database = Templates.objects.filter(email=request.user)
        template_value = list(template_database.values_list('templates', flat=True))
        # Assuming fetch_templates and display_whatsapp_id are defined elsewhere
        campaign_list = fetch_templates(display_whatsapp_id(request), token, None, False)
        if campaign_list is None :
            campaign_list=[]
        templates = [campaign for campaign in campaign_list if campaign['template_name'] in template_value]

        context = {
            "template_name": [template['template_name'] for template in templates],
            "template_data": json.dumps([template['template_data'] for template in templates]),
            "template_status": json.dumps([template['status'] for template in templates]),
            "carousel_nums": json.dumps([template['num_cards'] for template in templates]),
            "template_button": json.dumps([json.dumps(template['button']) for template in templates]),
            "template_media": json.dumps([template.get('media_type', 'No media available') for template in templates]),
            "template_images": json.dumps([template['media_link'] for template in templates]),
            "template_images_one": json.dumps([template['image_one'] for template in templates]),
            "template_images_two": json.dumps([template['image_two'] for template in templates]),
            "template_images_three": json.dumps([template['image_three'] for template in templates]),
            
        }
    except Exception as e:
        logger.error(f"Error fetching templates: {e}")
        context = {
            "template_name": [],
            "template_data": json.dumps([]),
            "template_status": json.dumps([]),
            "template_button": json.dumps([]),
            "template_media": json.dumps([]),
            "carousel_nums": json.dumps([])
        }

    context.update({
        "coins":request.user.marketing_coins + request.user.authentication_coins,
        "marketing_coins":request.user.marketing_coins,
        "authentication_coins":request.user.authentication_coins,
        "report_list": report_list,
        "campaign_list": campaign_list,
        "username": request.user.email if request.user.is_authenticated else None,
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request)
    })

    if request.method == 'POST':
        campaign_title = request.POST.get("campaign_title")
        tempalate_name = request.POST.get("params")
        add_91 = request.POST.get("add_91")
        uploaded_file = request.FILES.get("files", None)
        contacts = request.POST.get("contact_number", "").strip()
        
        media_id_list = []
        for i in range(0, 3):
            file = request.FILES.get(f'file_{i}')
            if file:
                try:
                    media_id, _ = process_media_file(file, display_phonenumber_id(request), token)
                    media_id_list.append(media_id)
                    time.sleep(0.5)
                except Exception as e:
                    messages.error(request, f"Error processing file {i}: {str(e)}")
                    continue
        template_details = fetch_templates(display_whatsapp_id(request), token, tempalate_name)
        
        if not campaign_title or not campaign_title:
            messages.error(request, "Flow name is required.")
            return render(request, "send-flow.html", context)

        discount = show_discount(request.user)
        all_contact, contact_list, _, _ = validate_phone_numbers(request,contacts, uploaded_file, discount, add_91)
        
        try:
            detailes = get_template_details(campaign_list, tempalate_name)
            category = detailes['category']
        except Exception as e:
            category = None
            logger.error(f"Failed get template category {str(e)}")
            
        coin_validation = validate_balance(request, len(all_contact), category)
        if not coin_validation:
            messages.error(request, "Insufficient balance. Recharge to continue our services.")
            return render(request, "send-carousel.html", context)
        try:
            send_carousel_messages_with_report(request, token, phone_id, tempalate_name, campaign_title, contact_list,all_contact,media_id_list, template_details)
        except Exception as e:
            logger.error(f"Error processing Flow form: {e}")
            messages.error(request, "There was an error processing your request.")
        return redirect('send_carousel_messages')
        
    return render(request, "send-carousel.html", context)