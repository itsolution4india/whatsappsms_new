import json, requests
from django.http import JsonResponse
from django.shortcuts import render, redirect
from ..models import CoinsHistory, ReportInfo, Notifications, CustomUser
from ..utils import logger
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET
import re
from datetime import datetime
from ..forms import CoinTransactionForm
import random
from django.contrib import messages
from .auth import admin_check
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from datetime import timedelta, datetime
from django.db.models.functions import TruncDate
from django.db.models import Sum

def custom_500(request, exception=None):
    return render(request, 'error.html', status=500)

def facebook_sdk_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            code = data.get('code')

            # Step 1: Exchange code for access token
            params = {
                'client_id': '490892730652855',  # Replace with your Facebook App ID
                'client_secret': '2a272b5573130b915db4bccc27caa34f',  # Replace with your Facebook App Secret
                'code': code,
                'redirect_uri': 'https://developers.facebook.com/apps/490892730652855/'
            }
            response = requests.get('https://graph.facebook.com/v20.0/oauth/access_token', params=params)
            logger.info(response.json())
            token_data = response.json()

            if 'access_token' not in token_data:
                return JsonResponse({'error': 'Failed to retrieve access token'}, status=400)

            access_token = token_data['access_token']

            # Step 2: Debug the access token
            debug_params = {
                'input_token': access_token,
                'access_token': 'EAAGZBdt7VWLcBO8nr7i8nChTcNXzWF9aNMjPYVjjKU7BbNfIJGETpZAJY3A2y9vLxzo4xZCace1xKiqG7jS7772Hpak96BPl360cG8Dzt83ujr8BSwGyUbNRS2mIjwZBfUwhNFKXtpFZC2QJ9Lh6OcKLRuoNJ1sAXGk2LZBkNu9BN7JSpBbTnU2vR6neoYv4FFUwZDZD'  # Replace with your Facebook App Access Token
            }
            debug_response = requests.get('https://graph.facebook.com/v20.0/debug_token', params=debug_params)
            debug_data = debug_response.json()
            logger.info(f"debug_data {debug_data}")

            if 'error' in debug_data:
                return JsonResponse({'error': debug_data['error']['message']}, status=400)

            # Step 3: Subscribe WhatsApp Business Account to an application
            waba_id =data.get('waba_id') # Replace with your WhatsApp Business Account ID
            logger.info(f"waba_id, {waba_id}")
            subscribe_endpoint = f'https://graph.facebook.com/v20.0/{waba_id}/subscribed_apps'
            subscribe_params = {
                'subscribed_fields': 'messages, messaging_postbacks, messaging_optins, messaging_referrals',  # Adjust fields as per your requirements
                'access_token': 'EAAGZBdt7VWLcBO8nr7i8nChTcNXzWF9aNMjPYVjjKU7BbNfIJGETpZAJY3A2y9vLxzo4xZCace1xKiqG7jS7772Hpak96BPl360cG8Dzt83ujr8BSwGyUbNRS2mIjwZBfUwhNFKXtpFZC2QJ9Lh6OcKLRuoNJ1sAXGk2LZBkNu9BN7JSpBbTnU2vR6neoYv4FFUwZDZD'  # Replace with your Business Integration System Token
            }
            subscribe_response = requests.post(subscribe_endpoint, params=subscribe_params)
            subscribe_data = subscribe_response.json()

            if 'success' in subscribe_data:
                # Retrieve the WABA ID from the session info (example assumes frontend sends WABA ID in JSON)
                waba_id = data.get('waba_id')
                logger.info(f"success waba_id {waba_id}")
                

                
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

def coins_history_list(request):
    # Handle custom date range
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    transaction_type = request.GET.get('type')

    if start_date and end_date:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        end_date_obj = datetime.today().date()
        start_date_obj = end_date_obj - timedelta(days=30)
        start_date = start_date_obj.strftime('%Y-%m-%d')
        end_date = end_date_obj.strftime('%Y-%m-%d')

    # Base query for coins history within range
    coins_query = CoinsHistory.objects.filter(
        user=request.user,
        created_at__date__range=(start_date_obj, end_date_obj)
    )
    
    # Apply transaction type filter if specified
    if transaction_type:
        coins_query = coins_query.filter(type=transaction_type)
    
    # Get ordered coins history
    coins_history_all = coins_query.order_by('-created_at')
    
    # Paginate the results
    paginator = Paginator(coins_history_all, 10)  # Show 10 transactions per page
    page = request.GET.get('page')
    try:
        coins_history = paginator.page(page)
    except PageNotAnInteger:
        coins_history = paginator.page(1)
    except EmptyPage:
        coins_history = paginator.page(paginator.num_pages)

    # Calculate totals for the bar chart (use the unfiltered query by type to show both credit and debit)
    base_query = CoinsHistory.objects.filter(
        user=request.user,
        created_at__date__range=(start_date_obj, end_date_obj)
    )
    
    # Get total credits and debits
    totals_by_type = (
        base_query
        .values('type')
        .annotate(total=Sum('number_of_coins'))
    )

    # Prepare simplified chart data with just two bars
    total_credits = 0
    total_debits = 0
    
    for entry in totals_by_type:
        if entry['type'] == 'credit':
            total_credits = entry['total'] or 0
        elif entry['type'] == 'debit':
            total_debits = entry['total'] or 0
    
    chart_data = {
        'labels': ['Credits', 'Debits'],
        'data': [total_credits, total_debits]
    }

    context = {
        "coins_history": coins_history,
        "start_date": start_date_obj,
        "end_date": end_date_obj,
        "transaction_type": transaction_type,
        "chart_data": json.dumps(chart_data)  # Serialize chart data for JavaScript
    }
    return render(request, 'coins_history_list.html', context)

@login_required
def access_denide(request):
    return render(request, "access_denide.html") 

@csrf_exempt
def notify_user(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            logger.info(f"Received notification: {data}")
            status = data.get('status')
            unique_id = data.get('unique_id')
            report_id = data.get('report_id')
            request_id = str(report_id)
            if status == 'completed' and unique_id and request_id:
                if request_id.startswith("MESSAGE") or request_id.startswith("FLOW") or request_id.startswith("CAROUSEL"):
                    try:
                        notification_instance = get_object_or_404(Notifications, request_id=request_id)
                        notification_instance.end_request_id = unique_id
                        notification_instance.save()
                        logger.info(f"Updated response {request_id} with unique_id {unique_id} in end_request_id")
                    except Exception as e:
                        logger.error(f"Failed to update Message end_request_id {str(e)}")
                else:
                    report_instance = get_object_or_404(ReportInfo, id=report_id)

                    report_instance.end_request_id = unique_id
                    report_instance.save()

                    logger.info(f"Updated report {report_id} with unique_id {unique_id} in end_request_id")

                return JsonResponse({"status": "success", "message": "Notification processed successfully"})
            else:
                return JsonResponse({"status": "error", "message": "Invalid data in notification"}, status=400)
        
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON: {e} {request}")
            return JsonResponse({"status": "error", "message": f"Failed to decode notification: {e}"}, status=400)
        except Exception as e:
            logger.error(f"Error processing notification: {e} {request}")
            return JsonResponse({"status": "error", "message": f"Failed to process notification: {e}"}, status=400)
    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=405)

@require_GET
def process_sms_request(request):
    # Get query parameters from the request
    user = request.GET.get('user')
    authkey = request.GET.get('authkey')
    sender = request.GET.get('sender')
    mobile = request.GET.get('mobile')
    text = request.GET.get('text')
    rpt = request.GET.get('rpt')
    output = request.GET.get('output')
    
    numbers = re.findall(r'\d+', text)
    otp = numbers[0]
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Print the extracted values
    logger.info(f"Time: {current_time}, Response: {user}, {authkey}, {sender}, {mobile}, {rpt}, {output}, {otp}")

    if otp:
        # Prepare the API URL with the extracted values
        api_url = f"http://103.104.73.186/api/pushsms?user={user}&authkey={authkey}&sender={sender}&mobile={mobile}&text=Dear+User%2C+%0A+Your+Login+One+Time+Password+is+{otp}%0A+KGVNNT&rpt={rpt}&output={output}"

        try:
            # Call the external API
            response = requests.get(api_url)

            # Log the API response
            logger.info(f"API Response: {response.text}")

            # Return a success response
            return JsonResponse({
                'status': 'success',
                'message': 'SMS sent successfully'
            })
        except requests.RequestException as e:
            logger.error(f"Error calling the API: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to send SMS',
                'error': str(e)
            })
    else:
        return JsonResponse({
            'status': 'error',
            'message': 'OTP not found in the text'
        })

@user_passes_test(admin_check)
def coin_transaction_view(request):
    form = CoinTransactionForm(request.POST or None)
    current_balance = None
    users = CustomUser.objects.all()

    if request.method == 'POST' and form.is_valid():
        user = form.cleaned_data['user']
        category = form.cleaned_data['category']
        transaction_type = form.cleaned_data['transaction_type']
        number_of_coins = form.cleaned_data['number_of_coins']

        # Fetch current category balance
        if category == 'marketing':
            current_balance = user.marketing_coins
        else:
            current_balance = user.authentication_coins

        # Credit/Debit Logic
        if transaction_type == 'debit':
            if current_balance < number_of_coins:
                messages.error(request, f"Insufficient {category} balance.")
                return redirect('coin_transaction')
            new_balance = current_balance - number_of_coins
            reason = f"{number_of_coins} coins have been deducted from your account for the {category.upper()} category."
        else:
            new_balance = current_balance + number_of_coins
            reason = f"{number_of_coins} coins have been credited to your account for {category.upper()} category. Your current balance is {new_balance}"

        # Update user balance
        if category == 'marketing':
            user.marketing_coins = new_balance
        else:
            user.authentication_coins = new_balance
        user.save()

        # Add history
        CoinsHistory.objects.create(
            user=str(user.username),
            type=transaction_type,
            number_of_coins=number_of_coins,
            reason=reason,
            transaction_id=str(random.randint(100000000, 999999999))
        )

        messages.success(request, "Transaction completed successfully.")
        return redirect('coin_transaction')

    return render(request, 'coin_transaction.html', {'form': form,'users': users})

def get_user_balance(request):
    user_id = request.GET.get('user_id')
    category = request.GET.get('category')
    user = CustomUser.objects.get(pk=user_id)

    if category == 'marketing':
        balance = user.marketing_coins
    else:
        balance = user.authentication_coins

    return JsonResponse({'balance': balance})