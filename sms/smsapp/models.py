from typing import Any
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
import random
from django.utils import timezone

class CustomUserManager(BaseUserManager):
    def create_user(self, email: str, username: str, password: str = None, **extra_fields: Any) -> 'CustomUser':
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user 

    def create_superuser(self, email: str, username: str, password: str = None, **extra_fields: Any) -> 'CustomUser':
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, username, password, **extra_fields)

def validate_digits(value: int, min_digits: int, max_digits: int):
    num_digits = len(str(value))
    if num_digits < min_digits:
        raise ValidationError(f'{value} has fewer than {min_digits} digits.')
    if num_digits > max_digits:
        raise ValidationError(f'{value} has more than {max_digits} digits.')

def validate_phone_number_id(value: str):
    if not value.isdigit() or len(value) != 15:
        raise ValidationError(f'{value} must be exactly 15 digits long.')

def validate_whatsapp_business_account_id(value: str):
    if not value.isdigit() or len(value) != 15:
        raise ValidationError(f'{value} must be exactly 15 digits long.')

class RegisterApp(models.Model):
    app_name = models.CharField(max_length=20)
    token = models.TextField()
    app_id = models.CharField(max_length=50)

    def __str__(self):
        return self.app_name

    def get_token(self):
        return self.token
    
    def get_app_id(self):
        return self.app_id

class CustomUser(AbstractBaseUser, PermissionsMixin):
    session_key = models.CharField(max_length=40, blank=True, null=True)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    phone_number_id = models.CharField(max_length=15, default=0, validators=[validate_phone_number_id])
    whatsapp_business_account_id = models.CharField(max_length=15,default=0, validators=[validate_whatsapp_business_account_id])
    coins = models.IntegerField(default=0, editable=False)
    marketing_coins = models.IntegerField(default=0)
    authentication_coins = models.IntegerField(default=0)
    discount = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    user_id = models.CharField(max_length=20, default='0')
    api_token = models.TextField(default='0')
    remarks = models.CharField(max_length=20, default='0')

    register_app = models.ForeignKey(RegisterApp, on_delete=models.SET_NULL, null=True)
    def save(self, *args, **kwargs):
        self.total_coins = self.marketing_coins + self.authentication_coins
        if self.register_app:
            # Set token and app_id from RegisterApp
            self.token = self.register_app.token
            self.app_id = self.register_app.app_id
        super(CustomUser, self).save(*args, **kwargs)
    @classmethod
    def get_app_info_by_email(cls, email):
        try:
            user = cls.objects.get(email=email)
            if user.register_app:
                return {
                    'token': user.register_app.token,
                    'app_id': user.register_app.app_id
                }
            else:
                return None
        except cls.DoesNotExist:
            return None
        
    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email



class Whitelist_Blacklist(models.Model):
    email = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    whitelist_phone = models.TextField()
    blacklist_phone = models.TextField()
    objects = CustomUserManager()



class ReportInfo(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    email = models.CharField(max_length=100)
    campaign_title=models.CharField(max_length=50)
    contact_list= models.TextField()
    message_date = models.DateField()
    template_name=models.CharField(max_length=100)
    message_delivery = models.IntegerField()
    start_request_id = models.IntegerField(default=0)
    end_request_id = models.IntegerField(default=0)
    


class Templates(models.Model):
    email = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    templates=models.CharField(unique=True,max_length=100)
    
class ScheduledMessage(models.Model):
    DAILY = 'Daily'
    ONCE = 'Once'
    
    SCHEDULE_TYPE_CHOICES = [
        (DAILY, 'Daily'),
        (ONCE, 'Once'),
    ]
    current_user = models.CharField(max_length=50)
    template_name = models.CharField(max_length=255)
    media_id = models.CharField(max_length=255, blank=True, null=True)
    all_contact = models.TextField()
    contact_list = models.TextField()
    campaign_title = models.CharField(max_length=255)
    schedule_date = models.CharField(max_length=50)
    schedule_time = models.CharField(max_length=50)
    schedule_type = models.CharField(
        max_length=5,
        choices=SCHEDULE_TYPE_CHOICES,
        default=ONCE,
    )
    admin_schedule = models.BooleanField(default=False)
    submitted_variables = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_sent = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.current_user} - {self.campaign_title} - {self.schedule_date} {self.schedule_time}"
    
class TemplateLinkage(models.Model):
    updated_at = models.DateTimeField(auto_now=True)
    template_name = models.CharField(max_length=255)
    button_name = models.CharField(max_length=100)
    useremail = models.CharField(max_length=100)
    linked_template_name = models.CharField(max_length=100)
    image_id = models.CharField(max_length=100)

    def __str__(self):
        return self.template_name
        
    
class MessageResponse(models.Model):
    MESSAGE_TYPES = [
        ('list_message', 'List Message'),
        ('reply_button_message', 'Reply Button Message'),
        ('single_product_message', 'Single Product Message'),
        ('multi_product_message', 'Multi Product Message'),
        ('send_my_location', 'Send My Location'),
        ('request_user_location', 'Request User Location'),
        ('link_template', 'Link Template'),
        ('send_text_message', 'Send Text Message')
    ]

    user = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    message_type = models.CharField(max_length=50, choices=MESSAGE_TYPES)
    user_response = models.CharField(max_length=255)
    body_message = models.TextField()

    sections = models.JSONField(default=dict, blank=True)
    product_section = models.JSONField(default=dict, blank=True)
    
    catalog_id = models.CharField(max_length=255, blank=True, null=True)
    product_retailer_id = models.CharField(max_length=255, blank=True, null=True)
    
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    template_name = models.CharField(max_length=255, blank=True, null=True)
    
    buttons = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'message_type']),
            models.Index(fields=['created_at']),
        ]
        unique_together = ['user', 'user_response']

    def __str__(self):
        return f"{self.message_type} - {self.user_response[:30]}"
        
class BotSentMessages(models.Model):
    MESSAGE_TYPES = [
        ('list_message', 'List Message'),
        ('reply_button_message', 'Reply Button Message'),
        ('single_product_message', 'Single Product Message'),
        ('multi_product_message', 'Multi Product Message'),
        ('send_my_location', 'Send My Location'),
        ('request_user_location', 'Request User Location'),
        ('link_template', 'Link Template'),
        ('send_text_message', 'Send Text Message')
    ]

    token = models.CharField(max_length=255)
    phone_number_id = models.CharField(max_length=255)
    contact_list = models.JSONField(default=list, blank=True, null=True)
    message_type = models.CharField(max_length=50, choices=MESSAGE_TYPES)
    header = models.TextField(blank=True, null=True)
    body = models.TextField()
    footer = models.TextField(blank=True, null=True)
    button_data = models.JSONField(default=dict, blank=True, null=True)
    product_data = models.JSONField(default=dict, blank=True, null=True)
    catalog_id = models.CharField(max_length=255, blank=True, null=True)
    sections = models.JSONField(default=list, blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    media_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone_number_id', 'message_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Message to {self.phone_number_id} - {self.message_type}"

class UserAccess(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    can_send_sms = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=False)
    can_manage_campaign = models.BooleanField(default=False)
    can_schedule_tasks = models.BooleanField(default=False)
    can_create_flow_message = models.BooleanField(default=False)
    can_send_flow_message = models.BooleanField(default=False)
    can_link_templates = models.BooleanField(default=False)
    can_manage_bot_flow = models.BooleanField(default=False)
    can_access_API_doc = models.BooleanField(default=False)
    can_manage_number_validation = models.BooleanField(default=False)
    can_enable_2fauth = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.email} - Access Rights"
        
class CoinsHistory(models.Model):
    CREDIT = 'credit'
    DEBIT = 'debit'
    TYPE_CHOICES = [
        (CREDIT, 'Credit'),
        (DEBIT, 'Debit'),
    ]

    user = models.CharField(max_length=100)
    type = models.CharField(max_length=6, choices=TYPE_CHOICES, default=CREDIT)
    number_of_coins = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(default='nan')
    transaction_id = models.CharField(max_length=9, unique=True, blank=True)  # For ITSXXXXXX

    def __str__(self):
        return f"{self.user} - {self.type} - {self.number_of_coins} - {self.transaction_id}"

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            # Generate a unique transaction_id with retry logic to ensure uniqueness
            while True:
                unique_code = random.randint(100000, 999999)
                new_transaction_id = f"ITS{unique_code}"
                
                if not CoinsHistory.objects.filter(transaction_id=new_transaction_id).exists():
                    self.transaction_id = new_transaction_id
                    break

        super(CoinsHistory, self).save(*args, **kwargs)
        
class Flows(models.Model):
    email = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    flows=models.CharField(unique=True,max_length=100)
    
class CountryPermission(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    can_send_msg_to_india = models.BooleanField(default=False)
    can_send_msg_to_nepal = models.BooleanField(default=False)
    can_send_msg_to_us = models.BooleanField(default=False)
    can_send_msg_to_australia = models.BooleanField(default=False)
    can_send_msg_to_uae = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.email} - Access Rights"
    
class Train_wit_Bot(models.Model):
    model_name = models.CharField(max_length=100)
    intent = models.CharField(unique=True,max_length=100)
    content = models.TextField(default='nan')
    
    def __str__(self):
        return self.intent
    
class Register_TwoAuth(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.CharField(max_length=200)
    email = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=12, default=0)
    
    def __str__(self):
        return self.user
    
class Validate_TwoAuth(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    email = models.CharField(max_length=200)
    otp = models.IntegerField(default=0)
    
    def __str__(self):
        return self.email
    
class Notifications(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    email = models.CharField(max_length=200)
    campaign_title = models.CharField(max_length=255, default="")
    start_request_id = models.CharField(max_length=100, default=0)
    end_request_id = models.CharField(max_length=100, default=0)
    request_id = models.CharField(max_length=100)
    text = models.CharField(max_length=200, default="")
    
    def __str__(self):
        return self.email
    
class Group(models.Model):
    user = models.CharField(max_length=200)
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Contact(models.Model):
    user = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=20, primary_key=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    groups = models.ManyToManyField(Group, related_name='contacts', blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.phone_number or self.name
    
class Last_Replay_Data(models.Model):
    id = models.AutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.CharField(max_length=200)
    number = models.CharField(max_length=15)
    name = models.CharField(max_length=200)
    count = models.CharField(max_length=3)
    last_count = models.CharField(max_length=3, default=0)
    last_updated = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, default='unread')
    
    def __str__(self):
        return f"{self.user} | {self.name} | {self.count}"