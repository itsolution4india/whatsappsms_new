import os
from wit import Wit
from django.shortcuts import render
from django.http import JsonResponse
import json
import requests
from ..utils import logger
from django.views.decorators.csrf import csrf_exempt
from ..models import ReportInfo
from django.urls import reverse
from django.shortcuts import redirect
from ..views import download_campaign_report

# Replace with your Wit.ai access token
WIT_AI_ACCESS_TOKEN = 'LIXVFYQNY4WISP5QLS2X6NJPEB57SHT2'

# Initialize Wit client
client = Wit(WIT_AI_ACCESS_TOKEN)

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
        if intent == 'greeting':
            return "Hello! How can I help you today?"
        elif intent == 'goodbye':
            return "Goodbye! Have a great day!"
        elif intent == 'ask_weather':
            return "I can help you with weather information. What city are you interested in?"
        elif intent == 'show_services':
            return "We offer services like custom software development, SaaS, cloud infrastructure, and digital transformation."
        
        elif intent == 'about_company':
            return "ItSolution4India is an IT services provider specializing in end-to-end software solutions."
        
        elif intent == 'contact_support':
            return "For support, please reach out through our contact form or email."

        elif intent == 'ask_about_saas':
            return "Our SaaS solutions focus on flexibility, scalability, and custom integration."

        elif intent == 'inquire_about_cloud_services':
            return "We offer cloud migration, management, and custom cloud applications to optimize your business."

        elif intent == 'request_project_discussion':
            return "We would love to discuss your project. Please schedule a consultation with our team."

        elif intent == 'request_demo':
            return "Request a demo to see how our services fit your business needs."

        elif intent == 'ask_industries_served':
            return "We serve industries like finance, healthcare, retail, and manufacturing."

        elif intent == 'request_automation_help':
            return "We provide automation tools to enhance productivity and streamline processes."

        elif intent == 'custom_software_inquiry':
            return "Yes, we specialize in building custom software tailored to your business needs."

        elif intent == 'consulting_services_inquiry':
            return "We offer consulting services to guide you through your digital transformation journey."

        elif intent == 'pricing_inquiry':
            return "Our pricing depends on your project requirements. Contact us for a custom quote."

        elif intent == 'schedule_meeting':
            return "Let’s set up a meeting to explore collaboration opportunities."

        elif intent == 'subscribe_newsletter':
            return "Subscribe to our newsletter to stay updated on our latest offerings."

        elif intent == 'data_analysis_help':
            return "We offer data analysis services to help you make data-driven decisions."

        elif intent == 'view_blog':
            return "Visit our blog for the latest insights and industry trends."

        elif intent == 'find_case_studies':
            return "Check out our case studies to see how we've helped other businesses succeed."

        elif intent == 'tech_stack_inquiry':
            return "We work with technologies like Python, Django, AWS, and more."

        elif intent == 'payment_integration_inquiry':
            return "We provide seamless payment gateway integration to support multiple transactions."

        elif intent == 'partnership_inquiry':
            return "We’re open to partnerships. Contact us to explore collaboration opportunities."
        
        elif intent == 'download_report':
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
                
                # Convert to dictionary and format the summary
                summary_dict = insight_data.groupby('status')['count'].sum().to_dict()
                
                # Create a human-readable summary string
                summary_parts = []
                total = sum(summary_dict.values())
                for status, count in summary_dict.items():
                    percentage = (count / total) * 100
                    summary_parts.append(f"{status}: {count} ({percentage:.1f}%)")
                
                full_summary = f"Total records: {total}\n" + "\n".join(summary_parts)
                
                return full_summary
            
            except Exception as e:
                logger.error(f"Error generating summary: {str(e)}")
                return "Unable to generate summary at this time."
        else:
            # Generic fallback response
            return f"{intent}"
    
    except Exception as e:
        logger.error(str(e))
        return f"Error processing message: {str(e)}"

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
