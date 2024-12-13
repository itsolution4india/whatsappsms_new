import os
from wit import Wit
from django.shortcuts import render
from django.http import JsonResponse
import json
import requests
from ..utils import logger
from django.views.decorators.csrf import csrf_exempt
from ..models import ReportInfo, Train_wit_Bot
from django.urls import reverse
from django.shortcuts import redirect
from ..views import download_campaign_report

# Replace with your Wit.ai access token
WIT_AI_ACCESS_TOKEN = 'LIXVFYQNY4WISP5QLS2X6NJPEB57SHT2'

# Initialize Wit client
client = Wit(WIT_AI_ACCESS_TOKEN)

def get_response(intent):
    try:
        response = Train_wit_Bot.objects.get(intent=intent)
        if response:
            return response.content
        else:
            return intent
    except Train_wit_Bot.DoesNotExist:
        return "I'm sorry, I don't understand that. How can I assist you?"

def process_wit_response(request, message):
    """
    Process message using Wit.ai and extract relevant information
    """
    logger.info(client.message(message))
    try:
        # Send message to Wit.ai and get response
        resp = client.message(message)
        
        # Extract intent and entities
        intent = resp.get('intents', [{}])[0].get('name', 'unknown')
        entities = resp.get('entities', {})
        logger.info(f"resp {resp}")
        # Basic response generation logic
        if intent == 'download_report':
            try:
                latest_report = ReportInfo.objects.filter(email=request.user.email).order_by('-id').first()
                download_url = f"/download_report/{latest_report.id}"
                return download_url
            
            except Exception as e:
                logger.error(f"Error in download_report intent: {str(e)}")
                return "Error occurred while trying to download the report."
        elif intent == 'summary':
            try:
                latest_report = ReportInfo.objects.filter(email=request.user.email).order_by('-id').first()
                insight_data = download_campaign_report(request, latest_report.id, insight=True)
                summary_lines = []
                for _, row in insight_data.iterrows():
                    summary_lines.append(f"{row['status']}\t{row['count']}")
                total = insight_data['count'].sum()
                summary_lines.append(f"Total Contacts\t{total}")
                full_summary = "\n".join(summary_lines)
                return full_summary
            
            except Exception as e:
                logger.error(f"Error generating summary: {str(e)}")
                return "Unable to generate summary at this time."
        else:
            response_message = get_response(intent)
            return response_message
    
    except Exception as e:
        logger.error(str(e))
        return f"We don't have the information for your query. Please contact support."

@csrf_exempt
def chat_with_bot(request):
    return render(request, "chat_with_bot.html")

def train_bot(request):
    return render(request, 'train.html')

@csrf_exempt
def chat(request):
    user_message = json.loads(request.body).get('message', '')
    
    bot_response = process_wit_response(request, user_message)
    logger.info(f"bot_response {bot_response}")
    
    return JsonResponse(bot_response, safe=False)

WIT_API_URL = 'https://api.wit.ai'

# Function to train utterance with intent
def train_utterance(utterance_data):
    url = f"{WIT_API_URL}/utterances?v=20240304"
    headers = {
        'Authorization': f"Bearer {WIT_AI_ACCESS_TOKEN}",
        'Content-Type': 'application/json'
    }
    response = requests.post(url, headers=headers, json=utterance_data)
    return response.json()

# Function to delete utterances
def delete_utterance(utterances):
    url = f"{WIT_API_URL}/utterances?v=20240304"
    headers = {
        'Authorization': f"Bearer {WIT_AI_ACCESS_TOKEN}",
        'Content-Type': 'application/json'
    }
    response = requests.delete(url, headers=headers, json=utterances)
    return response.json()

# Function to create an intent
def create_intent(intent_name):
    url = f"{WIT_API_URL}/intents?v=20240304"
    headers = {
        'Authorization': f"Bearer {WIT_AI_ACCESS_TOKEN}",
        'Content-Type': 'application/json'
    }
    intent_data = {"name": intent_name}
    response = requests.post(url, headers=headers, json=intent_data)
    return response.json()

# Function to get all intents
def get_intents():
    url = f"{WIT_API_URL}/intents?v=20240304"
    headers = {
        'Authorization': f"Bearer {WIT_AI_ACCESS_TOKEN}"
    }
    response = requests.get(url, headers=headers)
    logger.info(response.json())
    return response.json()

# Function to delete an intent
def delete_intent(intent_name):
    url = f"{WIT_API_URL}/intents/{intent_name}?v=20240304"
    headers = {
        'Authorization': f"Bearer {WIT_AI_ACCESS_TOKEN}"
    }
    response = requests.delete(url, headers=headers)
    return response.json()

def train(request):
    # Get form data for utterance and intent
    utterance_text = request.POST['utterance']
    intent_name = request.POST['intent']

    # Prepare data for training
    utterance_data = [{
        "text": utterance_text,
        "intent": intent_name,
        "entities": [],
        "traits": []
    }]
    
    # Call the function to train
    response = train_utterance(utterance_data)
    return JsonResponse(response, safe=False)

def delete_utterance_view(request):
    utterances = [{"text": request.POST['utterance']}]
    response = delete_utterance(utterances)
    return JsonResponse(response, safe=False)

def create_intent_view(request):
    intent_name = request.POST['intent']
    response = create_intent(intent_name)
    return JsonResponse(response, safe=False)

def delete_intent_view(request):
    intent_name = request.POST['intent']
    response = delete_intent(intent_name)
    return JsonResponse(response, safe=False)

def get_intents_view(request):
    response = get_intents()
    return JsonResponse(response, safe=False)
