import pandas as pd
from django.shortcuts import render, redirect
from django.http import JsonResponse
from ..models import Contact, Group
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from ..utils import display_whatsapp_id, display_phonenumber_id
from .auth import username

@login_required
def contact_management(request):
    contacts = Contact.objects.filter(user=request.user.email)
    groups = Group.objects.filter(user=request.user.email)
    return render(request, 'contact_management.html', {
        "coins": request.user.marketing_coins + request.user.authentication_coins,
        "marketing_coins": request.user.marketing_coins,
        "authentication_coins": request.user.authentication_coins,
        "username": username(request),
        "WABA_ID": display_whatsapp_id(request),
        "PHONE_ID": display_phonenumber_id(request),
        'contacts': contacts,
        'groups': groups
    })

@login_required
def create_contact(request):
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        name = request.POST.get('name', '')
        
        try:
            contact = Contact.objects.create(
                user=request.user.email,
                phone_number=phone_number,
                name=name
            )
            return JsonResponse({
                'status': 'success', 
                'message': 'Contact created successfully',
                'contact': {
                    'phone_number': contact.phone_number,
                    'name': contact.name
                }
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error', 
                'message': str(e)
            })
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@login_required
def upload_contacts_csv(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        df = pd.read_csv(csv_file)
        
        created_contacts = []
        for _, row in df.iterrows():
            phone_number = str(row.get('phone_number', '')).strip()
            name = str(row.get('name', '')).strip()
            
            if phone_number:
                contact, created = Contact.objects.get_or_create(
                    user=request.user,
                    phone_number=phone_number,
                    defaults={'name': name}
                )
                created_contacts.append({
                    'phone_number': contact.phone_number,
                    'name': contact.name,
                    'created': created
                })
        
        return JsonResponse({
            'status': 'success', 
            'contacts': created_contacts
        })
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@login_required
def create_group(request):
    if request.method == 'POST':
        group_name = request.POST.get('group_name')
        csv_file = request.FILES.get('csv_file')
        
        try:
            group = Group.objects.create(
                user=request.user.email,
                name=group_name
                )
            
            if csv_file:
                df = pd.read_csv(csv_file)
                for _, row in df.iterrows():
                    phone_number = str(row.get('phone_number', '')).strip()
                    name = str(row.get('name', '')).strip()
                    
                    if phone_number:
                        contact, _ = Contact.objects.get_or_create(
                            user=request.user,
                            phone_number=phone_number,
                            defaults={'name': name}
                        )
                        group.contacts.add(contact)
            
            return JsonResponse({
                'status': 'success', 
                'group': {
                    'id': group.id,
                    'name': group.name
                }
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error', 
                'message': str(e)
            })
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@login_required
@require_http_methods(["DELETE"])
def delete_contact(request, phone_number):
    try:
        contact = Contact.objects.get(
            user=request.user,
            phone_number=phone_number
            )
        contact.delete()
        return JsonResponse({'status': 'success', 'message': 'Contact deleted'})
    except Contact.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Contact not found'}, status=404)

@login_required
@require_http_methods(["DELETE"])
def delete_group(request, group_id):
    try:
        group = Group.objects.get(
            user=request.user,
            id=group_id
            )
        group.delete()
        return JsonResponse({'status': 'success', 'message': 'Group deleted'})
    except Group.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Group not found'}, status=404)

@login_required    
@require_http_methods(["POST"])
def add_contact_to_group(request):
    try:
        phone_number = request.POST.get('phone_number')
        group_id = request.POST.get('group_id')

        contact = Contact.objects.get(
            user=request.user,
            phone_number=phone_number
            )
        group = Group.objects.get(
            user=request.user,
            id=group_id
            )

        # Add contact to group if not already in it
        group.contacts.add(contact)

        return JsonResponse({
            'status': 'success',
            'message': f'Contact added to {group.name}',
            'group_name': group.name
        })
    except Contact.DoesNotExist:
        return JsonResponse({
            'status': 'error', 
            'message': 'Contact not found'
        }, status=404)
    except Group.DoesNotExist:
        return JsonResponse({
            'status': 'error', 
            'message': 'Group not found'
        }, status=404)

@login_required
@require_http_methods(["GET"])
def get_group_contacts(request, group_id):
    try:
        group = Group.objects.get(
            user=request.user,
            id=group_id
            )
        contacts = group.contacts.all()
        
        contact_list = [{
            'phone_number': contact.phone_number,
            'name': contact.name or 'N/A'
        } for contact in contacts]

        return JsonResponse({
            'status': 'success',
            'group_name': group.name,
            'contacts': contact_list
        })
    except Group.DoesNotExist:
        return JsonResponse({
            'status': 'error', 
            'message': 'Group not found'
        }, status=404)

@login_required
@require_http_methods(["POST"])
def remove_contact_from_group(request):
    try:
        phone_number = request.POST.get('phone_number')
        group_id = request.POST.get('group_id')

        contact = Contact.objects.get(
            user=request.user,
            phone_number=phone_number
            )
        group = Group.objects.get(
            user=request.user,
            id=group_id
            )

        # Remove contact from group
        group.contacts.remove(contact)

        return JsonResponse({
            'status': 'success',
            'message': f'Contact removed from {group.name}',
            'group_name': group.name
        })
    except Contact.DoesNotExist:
        return JsonResponse({
            'status': 'error', 
            'message': 'Contact not found'
        }, status=404)
    except Group.DoesNotExist:
        return JsonResponse({
            'status': 'error', 
            'message': 'Group not found'
        }, status=404)

@login_required        
@require_http_methods(["GET"])
def get_available_contacts(request, group_id):
    try:
        group = Group.objects.get(id=group_id)
        
        # Get contacts not already in this group
        available_contacts = Contact.objects.exclude(groups=group)
        
        contact_list = [{
            'phone_number': contact.phone_number,
            'name': contact.name or ''
        } for contact in available_contacts]

        return JsonResponse({
            'status': 'success',
            'contacts': contact_list
        })
    except Group.DoesNotExist:
        return JsonResponse({
            'status': 'error', 
            'message': 'Group not found'
        }, status=404)