import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import random
import string
from ..models import Register_TwoAuth, Validate_TwoAuth
from ..fastapidata import send_api
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '../../sms/.env'))

def generate_otp():
    """Generate a 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))

@csrf_exempt
@require_http_methods(["POST"])
def generate_otp_view(request):
    try:
        data = json.loads(request.body)
        email = data.get('email')
        phone = data.get('phone')
        
        if not email or not phone:
            return JsonResponse({
                'success': False,
                'message': 'Email and phone number are required'
            })
        
        # Generate OTP
        otp = generate_otp()
        print(otp)
        
        # Store OTP in session for verification
        request.session['otp'] = otp
        request.session['email'] = email
        request.session['phone'] = phone
        
        # Try to get existing record or create new one
        try:
            validate_record = Validate_TwoAuth.objects.get(email=email)
            # Update existing record
            validate_record.otp = otp
            validate_record.save()
            print(os.getenv('TOKEN'), os.getenv('PHONEID'), "authtemp01", "en", "OTP", None, [str(phone)], [str(otp)])
            response = send_api(os.getenv('TOKEN'), os.getenv('PHONEID'), "authtemp01", "en", "OTP", None, [str(phone)], [str(otp)], True)
            print("response", response.json())
        except Validate_TwoAuth.DoesNotExist:
            # Create new record
            Validate_TwoAuth.objects.create(
                email=email,
                otp=otp
            )
        
        print(f"OTP for {email}: {otp}")
        
        return JsonResponse({
            'success': True,
            'message': 'OTP generated successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

@csrf_exempt
@require_http_methods(["POST"])
def register_2fa_view(request):
    try:
        data = json.loads(request.body)
        email = data.get('email')
        phone = data.get('phone')
        otp = data.get('otp')
        
        # Verify OTP
        stored_otp = request.session.get('otp')
        stored_email = request.session.get('email')
        stored_phone = request.session.get('phone')
        
        if not stored_otp or not stored_email or not stored_phone:
            return JsonResponse({
                'success': False,
                'message': 'Session expired. Please request a new OTP'
            })
            
        if otp != stored_otp or email != stored_email or phone != stored_phone:
            return JsonResponse({
                'success': False,
                'message': 'Invalid OTP or details'
            })
        
        user = request.user.username if request.user.is_authenticated else 'Anonymous'
        Register_TwoAuth.objects.create(
            user=user,
            email=email,
            phone_number=phone
        )
            
        # Clear session data
        del request.session['otp']
        del request.session['email']
        del request.session['phone']
        
        return JsonResponse({
            'success': True,
            'message': '2FA enabled successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })
        
@csrf_exempt
@require_http_methods(["POST"])
def disable_2fa(request):
    if request.user.is_authenticated:
        try:
            user_2fa = Register_TwoAuth.objects.get(user=request.user.username)
            user_2fa.delete()
            
            return JsonResponse({
                'success': True,
                'message': '2FA disabled successfully'
            })
        except Register_TwoAuth.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '2FA is not enabled for this user'
            })
    else:
        return JsonResponse({
            'success': False,
            'message': 'User not authenticated'
        })