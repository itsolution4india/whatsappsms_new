from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from .models import CustomUser,Whitelist_Blacklist,ReportInfo,Templates, RegisterApp, ScheduledMessage, TemplateLinkage, MessageResponse, UserAccess, CoinsHistory, Flows
from .emailsend import main_send
from django.utils.html import format_html
from django import forms
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'user_id','username','phone_number_id','whatsapp_business_account_id','coins','discount', 'is_staff', 'register_app')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('email', 'username')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email','user_id','phone_number_id','whatsapp_business_account_id','coins','discount', 'password', 'register_app', 'api_token')}),
        (_('Personal info'), {'fields': ('username',)}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff','is_superuser', 'groups', 'user_permissions')}),
        
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'user_id','username','phone_number_id','whatsapp_business_account_id','coins','discount', 'password1', 'password2', 'is_active', 'is_staff', 'is_superuser', 'register_app'),
        }),
    )
 

   
   
    def save_model(self, request, obj, form, change):
        # Get the original object from the database (if it exists)
        if change:
            orig_obj = self.model.objects.get(pk=obj.pk)
            # Check if certain fields have changed (e.g., email)
            if obj.email != orig_obj.email:
                new_mail=obj.email
                old_mail=orig_obj.email
                main_send(new_mail,old_mail)      
        # Save the object
        super().save_model(request, obj, form, change)

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(RegisterApp)
class WhitelistBlacklistAdminForm(forms.ModelForm):
    class Meta:
        model = Whitelist_Blacklist
        fields = '__all__'
        widgets = {
            'whitelist_phone': forms.Textarea(attrs={'placeholder': '+9197857XXXXX'}),
            'blacklist_phone': forms.Textarea(attrs={'placeholder': '+9197857XXXXX'}),
        }

class Whitelist_BlacklistAdmin(admin.ModelAdmin):
    list_display = ('whitelist_phone', 'blacklist_phone')
    search_fields = ('whitelist_phone', 'blacklist_phone')
    
    fieldsets = (
        (None, {
            'fields': ('whitelist_phone', 'blacklist_phone'),
            'description': "Enter new phone numbers to be whitelist and blacklist, each on a new line."
        }),
    )
    form = WhitelistBlacklistAdminForm

admin.site.register(Whitelist_Blacklist, Whitelist_BlacklistAdmin)


class ReportInfoAdmin(admin.ModelAdmin):
    list_display = (
        'email',
        "campaign_title",
        'template_name',
        'message_date',
        'message_delivery',
        "contact_list",
        
        

    )
    list_filter = (
        'email',
        'message_date',
    )
    search_fields = (
        'email__email',
    )
    date_hierarchy = 'message_date'
    ordering = ('-message_date',)

    fields = (
        'email',
        "campaign_title",
        "contact_list",
        'message_date',
        'message_delivery',
        'template_name',
      
 
    )



admin.site.register(ReportInfo, ReportInfoAdmin)


class TemplatesAdmin(admin.ModelAdmin):
    list_display = (
        'email',
        'templates',
    )
    list_filter = (
        'email',
    )
    search_fields = (
        'email__email',
    )
    fieldsets = (
        (None, {
            'fields': (
                'email',
                'templates',
            ),
        }),
    )

class UserAccessAdmin(admin.ModelAdmin):
    list_display = ('user', 'can_send_sms', 'can_view_reports', 'can_manage_campaign', 'can_schedule_tasks', 'can_create_flow_message', 'can_send_flow_message', 'can_link_templates', 'can_manage_bot_flow')

# Register your admin class with the model
admin.site.register(Templates, TemplatesAdmin)
admin.site.register(ScheduledMessage)
admin.site.register(TemplateLinkage)
admin.site.register(MessageResponse)
admin.site.register(UserAccess, UserAccessAdmin)
admin.site.register(CoinsHistory)
admin.site.register(Flows)