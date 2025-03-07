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


from django.db.models import Prefetch

@login_required
def link_templates(request):
    if not check_user_permission(request.user, 'can_link_templates'):
        return redirect("access_denide")
    
    df = get_user_responses(request)
    df['phone_number_id'] = df['phone_number_id'].astype(str).str.replace(r'\.0$', '', regex=True)

    # Fetch token and app_id once
    token, app_id = get_token_and_app_id(request)
    campaign_list = fetch_templates(display_whatsapp_id(request), token) or []

    # Prefetch related data to avoid redundant queries
    report_list = ReportInfo.objects.filter(email=request.user).only('contact_list')
    
    templatelinkage = TemplateLinkage.objects.filter(useremail=request.user)
    button_names = list(templatelinkage.values_list('button_name', flat=True))

    templatelinkage_with_counts = []
    if button_names:
        # Calculate counts for all buttons at once using vectorized operations
        df_lower = df['message_body'].str.lower().fillna('')
        counts = df_lower.apply(lambda body: [body.count(button.lower()) for button in button_names]).sum(axis=0)

        for linkage, count in zip(templatelinkage, counts):
            templatelinkage_with_counts.append({
                'id': linkage.id,
                'template_name': linkage.template_name,
                'button_name': linkage.button_name,
                'linked_template_name': linkage.linked_template_name,
                'image_id': linkage.image_id,
                'count': count
            })

    template_database = Templates.objects.filter(email=request.user)
    template_value = set(template_database.values_list('templates', flat=True))

    templates = [campaign for campaign in campaign_list if campaign['template_name'] in template_value]

    # Create context in one go, avoiding multiple iterations for json.dumps
    context = {
        "coins": request.user.marketing_coins + request.user.authentication_coins,
        "marketing_coins": request.user.marketing_coins,
        "authentication_coins": request.user.authentication_coins,
        "username": username(request),
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request),
        "template_name": [template['template_name'] for template in templates],
        "template_data": json.dumps([template['template_data'] for template in templates]),
        "template_status": json.dumps([template['status'] for template in templates]),
        "template_button": json.dumps([json.dumps(template['button']) for template in templates]),
        "template_media": json.dumps([template.get('media_type', 'No media available') for template in templates]),
        "campaign_list": campaign_list,
        "template_value": list(template_value),
        "templatelinkage": templatelinkage_with_counts,
        "report_list": report_list
    }

    if request.method == 'POST':
        template_name = request.POST.get('template_name')
        if not template_name:
            messages.error(request, "Template name is required.")
            return redirect('link_templates')

        header_type = request.POST.get('header_type')
        header_content = request.POST.get('header_content')

        media_ids = []
        linkages_to_create = []  # Prepare records for bulk insertion

        for i in range(1, 4):
            quick_reply = request.POST.get(f'quick_reply_{i}')
            linked_temp = request.POST.get(f'linked_temp_{i}')
            file = request.FILES.get(f'file_{i}')

            media_id, media_type = None, None
            if file:
                try:
                    media_id, media_type = process_media_file(file, display_phonenumber_id(request), token)
                except Exception as e:
                    messages.error(request, f"Error processing file {i}: {str(e)}")
                    continue

            media_id_str = f"{media_id}|{media_type}" if media_id else None
            media_ids.append(media_id_str)

            if quick_reply and linked_temp:
                linkages_to_create.append(TemplateLinkage(
                    template_name=template_name,
                    linked_template_name=linked_temp,
                    button_name=quick_reply,
                    useremail=request.user.email,
                    image_id=media_id_str or ''
                ))

        # Use bulk_create for faster insertion of multiple records
        if linkages_to_create:
            TemplateLinkage.objects.bulk_create(linkages_to_create)

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