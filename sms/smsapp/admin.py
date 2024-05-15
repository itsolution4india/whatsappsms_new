from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from .models import CustomUser,Whitelist_Blacklist,ReportInfo,CampaignData
from .emailsend import main_send
from django.utils.html import format_html
from django import forms
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'username', 'coins', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('email', 'username')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'coins', 'password')}),
        (_('Personal info'), {'fields': ('username',)}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'coins', 'password1', 'password2', 'is_active', 'is_staff', 'is_superuser'),
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
        'message_date',
        'message_delivery',
        'message_send',
        'message_failed',
        'report_file',
        'download_report',
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
        'message_date',
        'message_delivery',
        'message_send',
        'message_failed',
        'report_file',
        'original_filename',  
    )

    readonly_fields = ('original_filename',)  # Make original_filename read-only

    def download_report(self, obj):
        return '<a href="{}" download>Download</a>'.format(obj.report_file.url)
    download_report.allow_tags = True
    download_report.short_description = 'Download Report'

admin.site.register(ReportInfo, ReportInfoAdmin)


class CampaignDataAdmin(admin.ModelAdmin):
    list_display = [
        "email",
        "template_id",
        "sub_service",
        "template_data",
        "status",
        "uploaded_at",
        "voice_display",
        "text_display",
        "image_display",
        "pdf_display",
        "video_display",
    ]
    readonly_fields = ["voice", "text", "image", "pdf", "video"]
    fields = (
        "email",
        "template_id",
        "sub_service",
        "template_data",
        "status",
        "uploaded_at",
        "voice",
        "text",
        "image",
        "pdf",
        "video",
    )
    
    def voice_display(self, obj):
        if obj.voice:
            return format_html(
                '<audio controls><source src="{0}" type="audio/mpeg">Your browser does not support the audio element.</audio>',
                obj.voice.url,
            )
        return "No voice message"

    def image_display(self, obj):
        if obj.image:
            return format_html(
                '<img src="{0}" style="max-height: 200px; max-width: 200px;" />',
                obj.image.url,
            )
        return "No image"
    
    def text_display(self, obj):
        if obj.text:
            return format_html(
                '<a href="{0}">Download Text File</a>',
                obj.text.url,
            )
        return "No text file"

    def pdf_display(self, obj):
        if obj.pdf:
            return format_html(
                '<a href="{0}" target="_blank">Open PDF</a>', obj.pdf.url
            )
        return "No PDF"

    def video_display(self, obj):
        if obj.video:
            return format_html(
                '<video width="320" height="240" controls><source src="{0}" type="video/mp4">Your browser does not support the video tag.</video>',
                obj.video.url,
            )
        return "No video"

admin.site.register(CampaignData, CampaignDataAdmin)
