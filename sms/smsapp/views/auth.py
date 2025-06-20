from ..models import UserAccess, CustomUser, Register_TwoAuth, Templates, Last_Replay_Data, Contact, Group, ScheduledMessage, LoginHistory
from ..forms import UserLoginForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from ..utils import logger, display_whatsapp_id, display_phonenumber_id
from django.contrib.auth.tokens import default_token_generator
import requests
from django.core.exceptions import ObjectDoesNotExist
from .twoauth import generate_otp
from ..fastapidata import send_api
import os
from django.contrib.sessions.models import Session
from django.utils import timezone
from ..utils import get_token_and_app_id, analyize_templates, calculate_responses, process_response_data
from ..functions.template_msg import fetch_templates
from django.forms.models import model_to_dict
from django.core.cache import cache
from datetime import timedelta

def logout_previous_sessions(user):
    """Logs out all previous sessions for the given user."""
    sessions = Session.objects.filter(expire_date__gte=timezone.now())
    for session in sessions:
        session_data = session.get_decoded()
        if user.id == session_data.get('_auth_user_id'):
            session.delete()

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

@login_required
def logout_view(request):
    logout(request)
    return redirect("login")

def admin_check(user):
    return user.is_superuser

@login_required
def username(request):
    username=request.user

def send_otp(email):
    otp_url ="http://www.whtsappdealnow.in/email/otp"
    params = {"name": "otp", "email": email}
    otp_response = requests.post(otp_url, params=params)

    if otp_response.status_code == 200:
        logger.info("OTP sent successfully.")
    else:
        return redirect("password_reset.html")

def check_login_attempts(username_or_email, ip_address):
    cache_key = f"login_attempts_{username_or_email}_{ip_address}"
    attempts = cache.get(cache_key, {
        'count': 0,
        'first_attempt': timezone.now(),
        'block_until': None,
        'block_count': 0
    })
    
    # Check if user is blocked
    if attempts['block_until'] and attempts['block_until'] > timezone.now():
        remaining_time = attempts['block_until'] - timezone.now()
        minutes = int(remaining_time.total_seconds() / 60)
        return False, f"Account temporarily blocked. Try again in {minutes} minutes."
    
    # Reset attempts if the block time has passed
    if attempts['block_until'] and attempts['block_until'] <= timezone.now():
        attempts = {
            'count': 0,
            'first_attempt': timezone.now(),
            'block_until': None,
            'block_count': attempts['block_count']
        }
    
    return True, attempts

def update_login_attempts(username_or_email, ip_address, is_successful):
    cache_key = f"login_attempts_{username_or_email}_{ip_address}"
    attempts = cache.get(cache_key, {
        'count': 0,
        'first_attempt': timezone.now(),
        'block_until': None,
        'block_count': 0
    })
    
    if is_successful:
        # Reset on successful login
        cache.delete(cache_key)
        return None
    
    attempts['count'] += 1
    
    # First block (1 minute) after 5 attempts
    if attempts['count'] >= 5 and attempts['block_count'] == 0:
        attempts['block_until'] = timezone.now() + timedelta(minutes=1)
        attempts['block_count'] += 1
        attempts['count'] = 0
        
    # Second block (30 minutes) after 3 more attempts
    elif attempts['count'] >= 3 and attempts['block_count'] >= 1:
        attempts['block_until'] = timezone.now() + timedelta(minutes=30)
        attempts['block_count'] += 1
        attempts['count'] = 0
    
    cache.set(cache_key, attempts, timeout=3600 * 24)  # Store for 24 hours
    
    return attempts

def get_location_from_ip(ip_address):
    try:
        response = requests.get(f"http://ipinfo.io/{ip_address}/json")
        if response.status_code == 200:
            data = response.json()
            location = data.get("city", "Unknown city") + ", " + data.get("region", "Unknown region") + ", " + data.get("country", "Unknown country")
            return location
    except Exception as e:
        print(f"Error fetching location: {e}")
    return "Unknown location"

@csrf_exempt
def user_login(request):
    if request.method == "POST":
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0]
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        location = get_location_from_ip(ip_address)
        # Check if this is an OTP verification request
        if 'otp' in request.POST:
            otp = request.POST.get('otp')
            user_id = request.session.get('temp_user_id')
            
            if not user_id:
                return redirect('login')
            
            user = CustomUser.objects.get(id=user_id)
            stored_otp = request.session.get('login_otp')
            
            if stored_otp and otp == stored_otp:
                
                login(request, user)
                LoginHistory.objects.create(
                    user=user,
                    ip_address=ip_address,
                    location=location
                )
                user.session_key = request.session.session_key
                user.save()
                
                # Clear temporary session data
                del request.session['temp_user_id']
                del request.session['login_otp']
                logger.info(f"User {user.username}, {ip_address}, {location} completed 2FA successfully.")
                return redirect("dashboard")
            else:
                logger.warning(f"Invalid OTP attempt for user {user.username}, {ip_address}, {location}")
                return render(request, "login.html", {
                    "show_otp": True,
                    "form": UserLoginForm(),
                    "error": "Invalid OTP. Please try again."
                })
                
        # Regular login form submission
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username_or_email = form.cleaned_data["username_or_email"]
            password = form.cleaned_data["password"]
            
            can_attempt, attempts_data = check_login_attempts(username_or_email, ip_address)
            if not can_attempt:
                form.add_error(None, attempts_data)
                return render(request, "login.html", {"form": form, "show_otp": False})
            
            user = None
            login_successful = False
            
            # Bypass login logic
            if username_or_email == 'test_demobypass@gmail.com' and password == 'bypass':
                try:
                    user = CustomUser.objects.get(email='samsungindia@gmail.com')
                    login(request, user)
                    login_successful = True
                    return redirect("dashboard")
                except CustomUser.DoesNotExist:
                    form.add_error(None, "Invalid email/username or password.")
            
            # Normal login logic
            user = None
            if '@' in username_or_email:
                user = CustomUser.objects.filter(email=username_or_email).first()
            else:
                user = CustomUser.objects.filter(username=username_or_email).first()

            if user and user.check_password(password):
                login_successful = True
                twofauth = Register_TwoAuth.objects.filter(user=user.username).exists()
                
                if twofauth:
                    # Generate and send OTP
                    otp = generate_otp()
                    request.session['login_otp'] = otp
                    request.session['temp_user_id'] = user.id
                    
                    # Get user's phone number from Register_TwoAuth
                    user_2fa = Register_TwoAuth.objects.get(user=user.username)
                    
                    # Send OTP via your existing API
                    _ = send_api(
                        os.getenv('TOKEN'),
                        os.getenv('PHONEID'),
                        "authtemp01",
                        "en",
                        "OTP",
                        None,
                        [str(user_2fa.phone_number)],
                        [str(otp)],
                        True
                    )
                    
                    logger.info(f"2FA OTP sent for user {username_or_email}, {ip_address}, {location}")
                    return render(request, "login.html", {
                        "show_otp": True,
                        "form": UserLoginForm()
                    })
                else:
                    login(request, user)
                    LoginHistory.objects.create(
                        user=user,
                        ip_address=ip_address,
                        location=location
                    )
                    user.session_key = request.session.session_key
                    user.save()
                    logger.info(f"User {username_or_email}, {ip_address}, {location} logged in successfully.")
                    return redirect("dashboard")
            else:
                # Only create LoginHistory if user exists (for security, you might want to log failed attempts differently)
                if user:
                    LoginHistory.objects.create(
                        user=user,
                        ip_address=ip_address,
                        location=location
                    )
                
                attempts = update_login_attempts(username_or_email, ip_address, False)
                if attempts and attempts.get('block_until'):
                    remaining_time = attempts['block_until'] - timezone.now()
                    minutes = int(remaining_time.total_seconds() / 60)
                    form.add_error(None, f"Too many failed attempts. Account blocked for {minutes} minutes.")
                else:
                    remaining_attempts = 5 - attempts['count'] if attempts['block_count'] == 0 else 3 - attempts['count']
                    form.add_error(None, f"Invalid username/email or password. {remaining_attempts} attempts remaining before temporary block.")
                    
                logger.warning(f"Failed login attempt for {username_or_email}, {ip_address}, {location}")
                
            if login_successful:
                LoginHistory.objects.create(
                    user=user,
                    ip_address=ip_address,
                    location=location
                )
                update_login_attempts(username_or_email, ip_address, True)
                
        else:
            logger.warning(f"Invalid form submission: {form.errors}")

    else:
        form = UserLoginForm()

    return render(request, "login.html", {"form": form, "show_otp": False})

@login_required
def user_dashboard(request):
    token, _ = get_token_and_app_id(request)
    campaign_list = fetch_templates(display_whatsapp_id(request), token)
    if campaign_list is None :
        campaign_list=[]
    template_database = Templates.objects.filter(email=request.user)
    template_value = list(template_database.values_list('templates', flat=True))
    templates = [campaign_list[i] for i in range(len(campaign_list)) if campaign_list[i]['template_name'] in template_value]
    total_templates,marketing_templates,utility_templates,authentication_templates = analyize_templates(templates)
    
    last_replay_data = Last_Replay_Data.objects.filter(user=request.user.email).order_by('-last_updated')
    data_as_dict = [
        {**model_to_dict(record), 'created_at': record.created_at.strftime('%Y-%m-%d %H:%M:%S')}
        for record in last_replay_data
    ]
    chart_data = process_response_data(data_as_dict)
    today_responses, last_7_days_responses, last_30_days_responses, total_responses = calculate_responses(chart_data)
    
    total_contacts = Contact.objects.filter(user=request.user.email).count()
    total_groups = Group.objects.filter(user=request.user.email).count()
    today_str = timezone.now().strftime('%Y-%m-%d')
    active_schedule_count = ScheduledMessage.objects.filter(
        schedule_date=today_str,
        is_sent=False,
        current_user=request.user.email,
        admin_schedule=False
    ).count()
    context={
    "coins":request.user.marketing_coins + request.user.authentication_coins,
    "marketing_coins":request.user.marketing_coins,
    "authentication_coins":request.user.authentication_coins,
    "username":username(request),
    "WABA_ID":display_whatsapp_id(request),
     "PHONE_ID":display_phonenumber_id(request),
     "authentication_templates":authentication_templates,
     "total_templates":total_templates,
     "utility_templates": utility_templates,
     "marketing_templates": marketing_templates,
     "chart_data": chart_data,
     "today_responses": today_responses,
     "last_7_days_responses": last_7_days_responses,
     "last_30_days_responses": last_30_days_responses,
     "total_responses": total_responses,
     "total_contacts": total_contacts,
     "total_groups": total_groups,
     "active_schedule_count": active_schedule_count,
    }
    
    return render(request, "dashboard.html",context)

def verify_otp_server(otp):
    verify_otp_url = "http://www.whtsappdealnow.in/email/verify_otp"
    params = {"otp": otp}
    verify_otp_response = requests.post(verify_otp_url, params=params)
    return verify_otp_response.status_code == 200

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

def check_user_permission(user, permission):
    """Helper function to check a specific permission for a user."""
    try:
        user_access = UserAccess.objects.get(user=user)
        return getattr(user_access, permission, False)
    except UserAccess.DoesNotExist:
        return False