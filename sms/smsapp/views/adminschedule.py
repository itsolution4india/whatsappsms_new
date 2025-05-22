from pytz import timezone as pytz_timezone
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
import ast

from ..models import CustomUser,Templates,ScheduledMessage
def admin_check(user):
    return user.is_superuser

@user_passes_test(admin_check, login_url='/accounts/login/')
def admin_schedule(request):
    users = CustomUser.objects.all()
    selected_user = None
    templates = []
    editing_campaign = None
    
    # Get selected user ID (from GET for dropdown change, or POST for form submission)
    user_id = request.GET.get('user_id') or request.POST.get('user_id')
    
    if user_id:
        try:
            selected_user = CustomUser.objects.get(email=user_id)
            templates = Templates.objects.filter(email=selected_user)
        except CustomUser.DoesNotExist:
            selected_user = None
            templates = []
    
    # Handle edit mode
    edit_id = request.GET.get('edit')
    if edit_id:
        try:
            editing_campaign = ScheduledMessage.objects.get(id=edit_id)
            # Auto-select the user associated with this campaign
            if editing_campaign.current_user:
                try:
                    selected_user = CustomUser.objects.get(email=editing_campaign.current_user)
                    templates = Templates.objects.filter(email=selected_user)
                except CustomUser.DoesNotExist:
                    pass
            # Convert contact list back to original format for editing
            if editing_campaign.contact_list:
                # Check if we have original_contacts stored, otherwise convert from processed format
                if hasattr(editing_campaign, 'original_contacts') and editing_campaign.original_contacts:
                    editing_campaign.contacts = '\n'.join(editing_campaign.original_contacts)
                else:
                    # Convert processed numbers back to display format (remove country code for display)
                  display_contacts = []

# Convert the stringified list to an actual list
                contact_list = ast.literal_eval(editing_campaign.contact_list)

                for contact in contact_list:
                    if contact.startswith('91') and len(contact) == 12:
                        display_contacts.append(contact[2:])  # remove country code for display
                    else:
                        display_contacts.append(contact)

                editing_campaign.contacts = display_contacts
        except ScheduledMessage.DoesNotExist:
            editing_campaign = None
    
    schedules = ScheduledMessage.objects.filter(admin_schedule=True).order_by('-created_at')
    print(schedules)
    
    # Handle delete
    query = request.GET.get('delete')
    if query:
        try:
            ScheduledMessage.objects.get(id=query).delete()
            return redirect('admin_schedule')  # Redirect to prevent re-deletion on refresh
        except ScheduledMessage.DoesNotExist:
            pass
    print(query)
    
    if request.method == 'POST' and request.user.is_superuser:
        user = request.POST.get('user_id')
        template_id = request.POST.get('template_id')
        contacts = request.POST.get('contacts')
        schedule_type = request.POST.get('schedule_type')
        campaign_title = request.POST.get('campaign_title')
        edit_id = request.POST.get('edit_id')  # Check if this is an edit
        
        # Validation errors list
        validation_errors = []
        
        # Validate required fields
        if not user:
            validation_errors.append("Please select a user")
        if not template_id:
            validation_errors.append("Please select a template")
        if not schedule_type:
            validation_errors.append("Please select a schedule type")
        if not campaign_title or not campaign_title.strip():
            validation_errors.append("Please enter a campaign title")
        if not contacts or not contacts.strip():
            validation_errors.append("Please enter at least one contact number")
        
        # Process and validate contacts
        formatted_contacts = []
        original_contacts = []  # Store original format for editing
        invalid_contacts = []
        
        if contacts:
            contact_lines = [line.strip() for line in contacts.splitlines() if line.strip()]
            
            if not contact_lines:
                validation_errors.append("Please enter at least one contact number")
            elif len(contact_lines) > 100:  # Limit number of contacts
                validation_errors.append("Too many contacts. Maximum 100 contacts allowed")
            else:
                for i, number in enumerate(contact_lines, 1):
                    original_number = number  # Store the original input
                    # Remove spaces, dashes, parentheses, and other non-digit characters
                    cleaned = ''.join(filter(str.isdigit, number))
                    
                    # Validate phone number
                    if not cleaned:
                        invalid_contacts.append(f"Line {i}: '{number}' - No digits found")
                        continue
                    
                    # Check if it's a valid Indian mobile number
                    if len(cleaned) == 10:
                        # Indian mobile numbers start with 6, 7, 8, or 9
                        if cleaned[0] in '6789':
                            processed_number = '91' + cleaned  # Add country code for processing
                        else:
                            invalid_contacts.append(f"Line {i}: '{number}' - Invalid Indian mobile number")
                            continue
                    elif len(cleaned) == 12 and cleaned.startswith('91'):
                        # Already has country code, validate the mobile part
                        mobile_part = cleaned[2:]
                        if len(mobile_part) != 10 or mobile_part[0] not in '6789':
                            invalid_contacts.append(f"Line {i}: '{number}' - Invalid Indian mobile number")
                            continue
                        processed_number = cleaned
                    elif len(cleaned) == 11 and cleaned.startswith('0'):
                        # Remove leading 0 and add country code
                        mobile_part = cleaned[1:]
                        if len(mobile_part) == 10 and mobile_part[0] in '6789':
                            processed_number = '91' + mobile_part
                        else:
                            invalid_contacts.append(f"Line {i}: '{number}' - Invalid mobile number format")
                            continue
                    else:
                        invalid_contacts.append(f"Line {i}: '{number}' - Invalid number length or format")
                        continue
                    
                    # Check for duplicates in processed format
                    if processed_number in formatted_contacts:
                        invalid_contacts.append(f"Line {i}: '{number}' - Duplicate number")
                        continue
                    
                    formatted_contacts.append(processed_number)
                    original_contacts.append(original_number)  # Store original format
        
        # Add contact validation errors
        if invalid_contacts:
            validation_errors.extend(invalid_contacts)
        
        # If there are validation errors, return with errors
        if validation_errors:
            error_message = "Please fix the following errors:\n" + "\n".join(f"• {error}" for error in validation_errors)
            return render(request, 'adminschedule.html', {
                'users': users,
                'selected_user': selected_user,
                'templates': templates,
                'schedules': schedules,
                'editing_campaign': editing_campaign,
                'error_message': error_message,
                'form_data': {
                    'campaign_title': campaign_title,
                    'template_id': template_id,
                    'schedule_type': schedule_type,
                    'contacts': contacts,
                }
            })
        
        print(f"Validated contacts: {formatted_contacts}")
        
        # Calculate schedule date and time
        india_timezone = pytz_timezone('Asia/Kolkata')
        now = datetime.now(india_timezone)
        
        if schedule_type == 'Daily':
            schedule_date = (now + timedelta(days=1)).date()  # tomorrow
            schedule_time = datetime.strptime("08:00:00", "%H:%M:%S").time()
            # schedule_date = now.date()
            # schedule_time = (now + timedelta(minutes=3)).replace(second=0, microsecond=0).time()
        elif schedule_type == 'Hourly':
            schedule_date = now.date()
            schedule_time = (now + timedelta(minutes=3)).replace(second=0, microsecond=0).time()
        else:  # Once or custom
            schedule_date = now.date()
            schedule_time = now.time().replace(second=0, microsecond=0)
        
        print(user, template_id, contacts, schedule_type)
        
        # Check if this is an edit or new creation
        if edit_id:
            # Update existing campaign
            try:
                schedule_message = ScheduledMessage.objects.get(id=edit_id)
                schedule_message.current_user = user
                schedule_message.template_name = template_id
                schedule_message.schedule_type = schedule_type
                schedule_message.contact_list = formatted_contacts
                schedule_message.all_contact = formatted_contacts
                schedule_message.campaign_title = campaign_title
                schedule_message.schedule_date = schedule_date
                schedule_message.schedule_time = schedule_time
                
                # Store original contacts if the model supports it
                if hasattr(schedule_message, 'original_contacts'):
                    schedule_message.original_contacts = original_contacts
                
                schedule_message.save()
                success_message = f"Campaign '{campaign_title}' updated successfully! {len(formatted_contacts)} contacts validated and saved."
            except ScheduledMessage.DoesNotExist:
                error_message = "Campaign not found for update!"
                return render(request, 'adminschedule.html', {
                    'users': users,
                    'selected_user': selected_user,
                    'templates': templates,
                    'schedules': schedules,
                    'editing_campaign': editing_campaign,
                    'error_message': error_message,
                })
        else:
            # Create new campaign
            try:
                new_schedule = ScheduledMessage(
                    current_user=user,
                    template_name=template_id,
                    schedule_type=schedule_type,
                    contact_list=formatted_contacts,
                    all_contact=formatted_contacts,
                    campaign_title=campaign_title,
                    schedule_date=schedule_date,
                    schedule_time=schedule_time,
                    admin_schedule=True,
                    submitted_variables='[]'
                )
                
                # Store original contacts if the model supports it
                if hasattr(new_schedule, 'original_contacts'):
                    new_schedule.original_contacts = original_contacts
                
                new_schedule.save()
                success_message = f"Campaign '{campaign_title}' scheduled successfully! {len(formatted_contacts)} contacts validated and saved."
            except Exception as e:
                error_message = f"Error creating campaign: {str(e)}"
                return render(request, 'adminschedule.html', {
                    'users': users,
                    'selected_user': selected_user,
                    'templates': templates,
                    'schedules': schedules,
                    'editing_campaign': editing_campaign,
                    'error_message': error_message,
                    'form_data': {
                        'campaign_title': campaign_title,
                        'template_id': template_id,
                        'schedule_type': schedule_type,
                        'contacts': contacts,
                    }
                })
        
        # Redirect to clear the edit parameters and prevent form resubmission
        if edit_id:
            return redirect(f'/admin_schedule/?user_id={user}&success=updated')
        else:
            return render(request, 'adminschedule.html', {
                'users': users,
                'selected_user': selected_user,
                'templates': templates,
                'message': success_message,
                'schedules': ScheduledMessage.objects.filter(admin_schedule=True).order_by('-created_at'),
            })
    
    return render(request, 'adminschedule.html', {
        'users': users,
        'selected_user': selected_user,
        'templates': templates,
        'schedules': schedules,
        'editing_campaign': editing_campaign,
    })