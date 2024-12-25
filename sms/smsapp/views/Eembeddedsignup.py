from django.shortcuts import render
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

def signup_view(request):
    return render(request, 'signup.html')

@csrf_exempt
def process_signup(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        access_token = data.get('access_token')
        user_id = data.get('user_id')
        
        print(access_token)
        print(user_id)

        return JsonResponse({'status': 'success', 'message': 'Signup processed successfully'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)