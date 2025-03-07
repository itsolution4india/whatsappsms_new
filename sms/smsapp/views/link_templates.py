from django.contrib.auth.decorators import login_required
from ..utils import display_phonenumber_id, get_token_and_app_id, display_whatsapp_id, logger
from .auth import check_user_permission, username
from .reports import get_user_responses
from django.shortcuts import render, redirect
from ..functions.template_msg import header_handle
from ..functions.template_msg import header_handle, fetch_templates
from ..models import TemplateLinkage, Templates, ReportInfo
import json, time
from django.contrib import messages
from ..media_id import process_media_file
from django.shortcuts import get_object_or_404
import pandas as pd


@login_required
def link_templates(request):
    phone_id = display_phonenumber_id(request)
    if not check_user_permission(request.user, 'can_link_templates'):
        return redirect("access_denide")
    df = get_user_responses(request)
    # df = pd.read_csv(r"C:\Users\user\Downloads\webhook_responses.csv")
    df['phone_number_id'] = df['phone_number_id'].astype(str).str.replace(r'\.0$', '', regex=True)
    token, app_id = get_token_and_app_id(request)
    campaign_list = fetch_templates(display_whatsapp_id(request), token)
    if campaign_list is None:
        campaign_list = []

    report_list = ReportInfo.objects.filter(email=request.user).only('contact_list')
    
    templatelinkage = TemplateLinkage.objects.filter(useremail= request.user)
    button_names = list(templatelinkage.values_list('button_name', flat=True))
    if button_names:
        counts = [int(df['message_body'].str.lower().str.contains(button.lower()).fillna(False).sum()) for button in button_names]
        # Create a list of dictionaries combining templatelinkage and counts
        templatelinkage_with_counts = []
        for linkage, count in zip(templatelinkage, counts):
            linkage_dict = {
                'id': linkage.id,
                'template_name': linkage.template_name,
                'button_name': linkage.button_name,
                'linked_template_name': linkage.linked_template_name,
                'image_id': linkage.image_id,
                'count': count
            }
            templatelinkage_with_counts.append(linkage_dict)
    else:
        templatelinkage_with_counts = []
    
    # templatelinkage = zip(templatelinkage, counts)
    template_database = Templates.objects.filter(email=request.user)
    template_value = list(template_database.values_list('templates', flat=True))
    templates = [campaign for campaign in campaign_list if campaign['template_name'] in template_value]

    context = {
        "coins":request.user.marketing_coins + request.user.authentication_coins,
        "marketing_coins":request.user.marketing_coins,
        "authentication_coins":request.user.authentication_coins,
        "username": username(request),
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request),
        "template_name": [template['template_name'] for template in templates],
        "template_data": json.dumps([template['template_data'] for template in templates]),
        "template_status": json.dumps([template['status'] for template in templates]),
        "template_button": json.dumps([json.dumps(template['button']) for template in templates]),
        "template_media": json.dumps([template.get('media_type', 'No media available') for template in templates]),
        "campaign_list": campaign_list,
        "template_value": template_value,
        "templatelinkage": templatelinkage_with_counts,
        "report_list":report_list
    }

    if request.method == 'POST':
        template_name = request.POST.get('template_name')
        if not template_name:
            messages.error(request, "Template name is required.")
            return redirect('link_templates')

        header_type = request.POST.get('header_type')
        header_content = request.POST.get('header_content')

        media_ids = []
        for i in range(1, 4):
            quick_reply = request.POST.get(f'quick_reply_{i}')
            linked_temp = request.POST.get(f'linked_temp_{i}')
            file = request.FILES.get(f'file_{i}')

            media_id = None
            media_type = None
            if file:
                try:
                    media_id, media_type = process_media_file(file, display_phonenumber_id(request), token)
                    time.sleep(1.5)
                except Exception as e:
                    messages.error(request, f"Error processing file {i}: {str(e)}")
                    continue

            media_id_str = f"{media_id}|{media_type}" if media_id else None
            media_ids.append(media_id_str)

            if quick_reply and linked_temp:
                try:
                    TemplateLinkage.objects.create(
                        template_name=template_name,
                        linked_template_name=linked_temp,
                        button_name=quick_reply,
                        useremail=request.user.email,
                        image_id=media_id_str or ''
                    )
                except Exception as e:
                    messages.error(request, f"Error creating template linkage: {str(e)}")

        if header_type in ['headerImage', 'headerVideo', 'headerDocument', 'headerAudio']:
            try:
                header_content = header_handle(header_content, token, app_id)
            except Exception as e:
                messages.error(request, f"Error handling header: {str(e)}")

        messages.success(request, "Template linkages created successfully.")
        return redirect('link_templates')

    return render(request, "link_templates.html", context)

@login_required
def delete_template_linkage(request, id):
    linkage = get_object_or_404(TemplateLinkage, id=id, useremail=request.user)
    if request.method == 'POST':
        try:
            linkage.delete()
            messages.success(request, "Successfully Deleted")
        except Exception as e:
            messages.error(request, "Something went wrong, Try again later")
            logger.error(f"Error in deleting linked template  {e}")
        return redirect('link_templates')