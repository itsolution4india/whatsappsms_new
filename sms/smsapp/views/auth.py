from ..models import UserAccess, CustomUser
from ..forms import UserLoginForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from ..utils import logger, display_whatsapp_id, display_phonenumber_id
from django.contrib.auth.tokens import default_token_generator
import requests
from django.core.exceptions import ObjectDoesNotExist


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

@login_required
def username(request):
    username=request.user

def send_otp(email):
    otp_url ="http://www.whtsappdealnow.in/email/otp"
    params = {"name": "otp", "email": email}
    otp_response = requests.post(otp_url, params=params)

    if otp_response.status_code == 200:
        print("OTP sent successfully.")
    else:
        return redirect("password_reset.html")

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

@login_required
def user_dashboard(request):
    context={
    "coins":request.user.marketing_coins + request.user.authentication_coins,
    "marketing_coins":request.user.marketing_coins,
    "authentication_coins":request.user.authentication_coins,
    "username":username(request),
    "WABA_ID":display_whatsapp_id(request),
     "PHONE_ID":display_phonenumber_id(request)
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