from ..models import TemplateLinkage, Templates
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from ..create_template import template_create, create_auth_template
from ..functions.template_msg import fetch_templates, delete_whatsapp_template
from ..functions.send_messages import display_phonenumber_id
from ..utils import parse_fb_error, get_token_and_app_id, display_whatsapp_id, logger
from .auth import check_user_permission, username
from ..functions.template_msg import header_handle
import time
from ..media_id import process_media_file

@login_required
def Campaign(request):
    if not check_user_permission(request.user, 'can_manage_campaign'):
        return redirect("access_denide")
    token, app_id = get_token_and_app_id(request)
    campaign_list = fetch_templates(display_whatsapp_id(request), token)
    if campaign_list is None :
        campaign_list=[]
    template_database = Templates.objects.filter(email=request.user)
    template_value = list(template_database.values_list('templates', flat=True))
    templates = [campaign_list[i] for i in range(len(campaign_list)) if campaign_list[i]['template_name'] in template_value]

    context = {
        "template_value": template_value,
        "coins":request.user.marketing_coins + request.user.authentication_coins,
        "marketing_coins":request.user.marketing_coins,
        "authentication_coins":request.user.authentication_coins,
        "username": username(request),
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request),
        "campaign_list": templates,
        
    }

    if request.method == 'POST':
        template_name = request.POST.get('template_name')
        language = request.POST.get('language')
        category = request.POST.get('category')
        header_type = request.POST.get('actionHeaderType')
        header_content = None
        submitted_variables = []
        for key in request.POST:
                if key.startswith('var_input'):
                    submitted_variables.append(request.POST[key])
                    
        if header_type == 'headerText':
            header_content = request.POST.get('headerText', None)
        elif header_type == 'headerImage':
            header_content = request.FILES.get('headerImage', None)
        elif header_type == 'headerVideo':
            header_content = request.FILES.get('headerVideo', None)
        elif header_type == 'headerDocument':
            header_content = request.FILES.get('headerDocument', None)
        elif header_type == 'headerDocument':
            header_content = request.FILES.get('headerAudio', None)
        
        body_text = request.POST.get('template_data').replace('\n', '\n').replace('<b>', '*').replace('</b>', '*')
        footer_text = request.POST.get('footer_data')
        call_button_text = request.POST.get('callbutton', None)
        phone_number = request.POST.get('contactNumber', None)
        quick_reply_one = request.POST.get('quick_reply_one', None)
        quick_reply_two = request.POST.get('quick_reply_two', None)
        quick_reply_three = request.POST.get('quick_reply_three', None)
        url_button_text = request.POST.get('websitebutton', None)
        website_url = request.POST.get('websiteUrl')
        url_button_textTwo = request.POST.get('websitebuttonTwo', None)
        website_urlTwo = request.POST.get('websiteUrlTwo', None)
        linked_temp_one = request.POST.get('linked_temp_one', None)
        linked_temp_two = request.POST.get('linked_temp_two', None)
        linked_temp_three = request.POST.get('linked_temp_three', None)

        media_file_one = request.FILES.get('file_one', None)
        media_file_two = request.FILES.get('file_two', None)
        media_file_three = request.FILES.get('file_three', None)

        if media_file_one:
            media_id_one, media_type_one = process_media_file(media_file_one, display_phonenumber_id(request), token)
            time.sleep(1.5) 
        else:
            media_id_one, media_type_one = None, None

        if media_file_two:
            media_id_two, media_type_two = process_media_file(media_file_two, display_phonenumber_id(request), token)
            time.sleep(1.5) 
        else:
            media_id_two, media_type_two = None, None

        if media_file_three:
            media_id_three, media_type_three = process_media_file(media_file_three, display_phonenumber_id(request), token)
        else:
            media_id_three, media_type_three = None, None

        media_id_one = media_id_one + '|' + media_type_one if media_id_one else None
        media_id_two = media_id_two + '|' + media_type_two if media_id_two else None
        media_id_three = media_id_three + '|' + media_type_three if media_id_three else None

        if header_type in ['headerImage','headerVideo','headerDocument','headerAudio']:
            header_content = header_handle(header_content, token, app_id)
        
        if quick_reply_one and linked_temp_one:
            TemplateLinkage.objects.create(template_name=template_name, linked_template_name=linked_temp_one, button_name=quick_reply_one, useremail=request.user.email, image_id=media_id_one)

        if quick_reply_two and linked_temp_two:
            TemplateLinkage.objects.create(template_name=template_name, linked_template_name=linked_temp_two, button_name=quick_reply_two, useremail=request.user.email, image_id=media_id_two)

        if quick_reply_three and linked_temp_three:
            TemplateLinkage.objects.create(template_name=template_name, linked_template_name=linked_temp_three, button_name=quick_reply_three, useremail=request.user.email, image_id=media_id_three)
            
        try:
            if category == 'Authentication':
                status, response = create_auth_template(
                    waba_id=display_whatsapp_id(request),
                    access_token=token,
                    template_name=template_name,
                    languages=language
                )
            else:
                status,data=template_create(
                    token=token,
                    waba_id=display_whatsapp_id(request),
                    template_name=template_name,
                    language=language,
                    category=category,
                    header_type=header_type,
                    header_content=header_content,
                    body_text=body_text,
                    footer_text=footer_text,
                    call_button_text=call_button_text,
                    phone_number=phone_number,
                    url_button_text=url_button_text,
                    website_url=website_url,
                    url_button_textTwo=url_button_textTwo,
                    website_urlTwo=website_urlTwo,
                    quick_reply_one=quick_reply_one,
                    quick_reply_two=quick_reply_two,
                    quick_reply_three=quick_reply_three,
                    body_example_values = submitted_variables if submitted_variables else None
                )
            if status !=200:
                error_details = parse_fb_error(data)
                context.update({
                    "error": error_details,
                    "has_error": True
                })

            Templates.objects.create(email=request.user, templates=template_name)
            if status == 200:
                return redirect('create_message_temp')
        except Exception as e:
            context.update({
                "error": {
                    "type": "Unexpected Error",
                    "message": str(e),
                    "details": str(e)
                },
                "has_error": True
            })
        
    return render(request, "create_message_temp.html", context)

@login_required
def campaign_index(request):
    token, _ = get_token_and_app_id(request)
    campaign_list = fetch_templates(display_whatsapp_id(request), token)
    if campaign_list is None :
        campaign_list=[]
    template_database = Templates.objects.filter(email=request.user)
    template_value = list(template_database.values_list('templates', flat=True))
    templates = [campaign_list[i] for i in range(len(campaign_list)) if campaign_list[i]['template_name'] in template_value]
    context = {
        "coins":request.user.marketing_coins + request.user.authentication_coins,
        "marketing_coins":request.user.marketing_coins,
        "authentication_coins":request.user.authentication_coins,
        "username": username(request),  
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request),
        "campaign_list": templates
    }
    return render(request, "Campaign.html", context)

@login_required
def delete_template(request):
    token, _ = get_token_and_app_id(request)
    template_name = request.POST.get('template_name')
    template_id = request.POST.get('template_id')

    delete_result = delete_whatsapp_template(waba_id=display_whatsapp_id(request), token=token, template_name=template_name, template_id=template_id)
    
    if delete_result:
        logger.info(f"Template '{template_name}' deleted successfully.")
    else:
        logger.info(f"Failed to delete template '{template_name}'.")
    
    return redirect('campaign')