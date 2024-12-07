from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from ..models import ReportInfo,Templates, ScheduledMessage, CountryPermission, Whitelist_Blacklist
from ..media_id import get_media_format,generate_id
from django.contrib import messages
import json, re, openpyxl
from ..functions.template_msg import fetch_templates
from django.utils.timezone import now
from ..functions.send_messages import send_messages, display_phonenumber_id, save_schedule_messages
from ..utils import check_schedule_timings, validate_balance, get_token_and_app_id, display_whatsapp_id, logger, show_discount
from .auth import check_user_permission
from ..functions.flows import send_flow_messages_with_report




@login_required
def Send_Sms(request):
    if not check_user_permission(request.user, 'can_send_sms'):
        return redirect("access_denied")

    current_user = request.user
    ip_address = request.META.get("REMOTE_ADDR", "Unknown IP")
    token, _ = get_token_and_app_id(request)

    # Cache display ID lookups
    waba_id = display_whatsapp_id(request)
    phone_id = display_phonenumber_id(request)
    
    scheduled_times = ScheduledMessage.objects.filter(schedule_date=now().date()).values_list('schedule_time', flat=True)
    
    try:
        coins = current_user.coins
        report_list = ReportInfo.objects.filter(email=current_user)
        template_database = Templates.objects.filter(email=current_user)
        template_value = list(template_database.values_list('templates', flat=True))
        
        campaign_list = fetch_templates(waba_id, token) or []
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
        "coins": current_user.marketing_coins + current_user.authentication_coins,
        "marketing_coins": current_user.marketing_coins,
        "authentication_coins": current_user.authentication_coins,
        "report_list": report_list,
        "campaign_list": campaign_list,
        "username": current_user.email,
        "WABA_ID": waba_id,
        "PHONE_ID": phone_id
    })

    if request.method == "POST":
        try:
            # Ensure user is authenticated
            if not current_user.is_authenticated:
                messages.error(request, "User is not authenticated.")
                return render(request, "send-sms.html", context)

            # Retrieve POST data
            campaign_title = request.POST.get("campaign_title")
            template_name = request.POST.get("params")
            submitted_variables = [request.POST[key] for key in request.POST if key.startswith('variable')]
            
            # Handle media file
            media_file = request.FILES.get('file')
            media_id = None
            if media_file:
                file_extension = media_file.name.split('.')[-1]
                media_type = get_media_format(file_extension)
                media_id = generate_id(phone_id, media_type, media_file, token).get('id')

            uploaded_file = request.FILES.get("files")
            contacts = request.POST.get("contact_number", "").strip()
            action_type = request.POST.get("action_type")

            # Validate required fields
            if not campaign_title or not template_name:
                messages.error(request, "Campaign title and template name are required.")
                return render(request, "send-sms.html", context)
         
            # Process contacts and validate balance
            discount = show_discount(current_user)
            all_contact, contact_list = validate_phone_numbers(request, contacts, uploaded_file, discount)
            total_coins = current_user.marketing_coins + current_user.authentication_coins

            if not validate_balance(total_coins, len(contact_list)):
                messages.error(request, "Insufficient balance. Please update.")
                return render(request, "send-sms.html", context)

            logger.info(f"Send_Sms: {current_user}, {phone_id}, {template_name}, {media_id}, {all_contact}, {contact_list}, {campaign_title}, {submitted_variables}")

            # Send or schedule messages
            if action_type == "submit":
                send_messages(current_user, token, phone_id, campaign_list, template_name, media_id, all_contact, contact_list, campaign_title, request, submitted_variables)
            else:
                schedule_date = request.POST.get("schedule_date")
                schedule_time = request.POST.get("schedule_time")

                if result := check_schedule_timings(schedule_time):
                    messages.warning(request, f"The time {schedule_time} is busy. Please choose from these available options: {result}")
                else:
                    messages.success(request, "Message Scheduled Successfully")
                    save_schedule_messages(current_user, template_name, media_id, all_contact, contact_list, campaign_title, schedule_date, schedule_time, submitted_variables)

            return redirect('send-sms')
        except Exception as e:
            logger.error(f"Error processing form: {e}")
            messages.error(request, "There was an error processing your request.")
            return render(request, "send-sms.html", context)

    return render(request, "send-sms.html", context)

def validate_phone_numbers(request, contacts, uploaded_file, discount):
    # Define patterns based on user permissions
    def get_country_patterns(user):
        patterns = {}
        try:
            permissions = CountryPermission.objects.get(user=user)
        except CountryPermission.DoesNotExist:
            return patterns

        country_patterns = {
            'india': r"^\+?91\d{10}$",
            'nepal': r"^\+?977\d{9}$",
            'us': r"^\+?1\d{10}$",
            'australia': r"^\+?61\d{9}$",
            'uae': r"^\+?971\d{9}$",
        }

        # Map permissions to country patterns
        if permissions.can_send_msg_to_india:
            patterns['india'] = re.compile(country_patterns['india'])
        if permissions.can_send_msg_to_nepal:
            patterns['nepal'] = re.compile(country_patterns['nepal'])
        if permissions.can_send_msg_to_us:
            patterns['us'] = re.compile(country_patterns['us'])
        if permissions.can_send_msg_to_australia:
            patterns['australia'] = re.compile(country_patterns['australia'])
        if permissions.can_send_msg_to_uae:
            patterns['uae'] = re.compile(country_patterns['uae'])
        
        return patterns

    # Validate a phone number based on country patterns
    def validate_numbers(numbers, patterns):
        valid_numbers = set()
        for phone_number in numbers:
            phone_number = phone_number.strip()
            for country, pattern in patterns.items():
                if pattern.match(phone_number):
                    valid_numbers.add(phone_number)
                    break
        return valid_numbers

    # Parse contacts from input and uploaded file
    def parse_contacts(contacts, uploaded_file):
        numbers = set(contacts.split("\r\n")) if contacts else set()
        if uploaded_file:
            workbook = openpyxl.load_workbook(uploaded_file)
            sheet = workbook.active
            for row in sheet.iter_rows(min_col=1, max_col=1, min_row=1):
                for cell in row:
                    if cell.value is not None:
                        numbers.add(str(cell.value).strip())
        return numbers

    # Apply whitelist, blacklist, and discount logic
    def apply_filters(valid_numbers, whitelist, blacklist, discount):
        final_list = [num for num in valid_numbers if num in whitelist and num not in blacklist]
        non_whitelist = [num for num in valid_numbers if num not in whitelist and num not in blacklist]

        # Add numbers that qualify after discount
        final_list.extend(non_whitelist[:max(0, len(non_whitelist) - discount)])
        return final_list

    # Main function logic
    patterns = get_country_patterns(request.user)
    if not patterns:
        return [], []

    numbers_list = parse_contacts(contacts, uploaded_file)
    valid_numbers = validate_numbers(numbers_list, patterns)
    
    # Fetch whitelist and blacklist
    whitelist_number, blacklist_number = whitelist_blacklist(request)

    # Calculate discount based on valid numbers
    discount_count = (len(valid_numbers) * discount) // 100 if len(valid_numbers) > 100 else 0
    
    # Apply whitelist, blacklist, and discount logic
    final_list = apply_filters(valid_numbers, whitelist_number, blacklist_number, discount_count)

    # Save valid numbers in whitelist/blacklist DB if under discount threshold
    if len(valid_numbers) <= 100:
        phone_numbers_string = ",".join(valid_numbers)
        Whitelist_Blacklist.objects.create(email=request.user, whitelist_phone=phone_numbers_string)

    return list(valid_numbers), final_list

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
        uploaded_file = request.FILES.get("files", None)
        contacts = request.POST.get("contact_number", "").strip()
        if not campaign_title or not flow_name:
            messages.error(request, "Flow name is required.")
            return render(request, "send-flow.html", context)

        discount = show_discount(request.user)
        all_contact, contact_list = validate_phone_numbers(request,contacts, uploaded_file, discount)
        
        total_coins = request.user.marketing_coins + request.user.authentication_coins
        coin_validation = validate_balance(total_coins, len(contact_list))
        if not coin_validation:
            messages.error(request, "Insufficient balance. Please update.")
            return render(request, "send-flow.html", context)
        logger.info(f"Send_Flow: {current_user}, {phone_id}, {campaign_list}, {flow_name}, {all_contact}, {contact_list}, {campaign_title}")
        try:
            send_flow_messages_with_report(current_user, token, phone_id, campaign_list, flow_name, all_contact, contact_list,campaign_title, request)
        except Exception as e:
            logger.error(f"Error processing Flow form: {e}")
            messages.error(request, "There was an error processing your request.")
        return redirect('send_flow_message')
        
    return render(request, "send-flow.html", context)