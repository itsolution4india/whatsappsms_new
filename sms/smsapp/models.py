from typing import Any
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.utils.html import format_html
from django.core.validators import FileExtensionValidator, MaxValueValidator
from django.utils import timezone
import os

class CustomUserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user 

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, username, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    coins=models.IntegerField(default=0)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email
       
   



class Whitelist_Blacklist(models.Model):
    
    whitelist_phone = models.TextField()
    blacklist_phone = models.TextField()
    objects = CustomUserManager()



class ReportInfo(models.Model):
    email = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message_date = models.DateField()
    message_send = models.IntegerField()
    message_delivery = models.IntegerField()
    message_failed = models.IntegerField()
class ReportFile(models.Model):
    email = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    report_file = models.FileField(upload_to='reports/',null=True)
    original_filename = models.CharField(max_length=255, default=timezone.now().strftime('%Y-%m-%d-%H-%M-%S'))

    def save(self, *args, **kwargs):
        if not self.pk:  # Check if it's a new instance
        # Extract filename and extension
            filename = self.report_file.name.split('/')[-1]
            filename, extension = os.path.splitext(filename)

        # Append "Failed" to filename if message_failed > 0
            if self.message_failed > 0:
                filename += "_Failed"

        # Reconstruct the filename with timestamp and extension
            timestamp = timezone.now().strftime('%Y-%m-%d-%H-%M-%S')
            self.original_filename = f"{timestamp}_{filename}{extension}"

        super().save(*args, **kwargs)
    def __str__(self):
        return f"{self.email}"


class CampaignData(models.Model):
    email = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
    )

    template_id = models.CharField(max_length=100, primary_key=True)
    sub_service = models.CharField(max_length=100)
    media_type=models.CharField(max_length=100)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    template_data = models.TextField()
    ACTION_TYPES = (
        ('callToAction', 'Call to Action'),
        ('visitWebsite', 'Visit Website'),
    )

    action_type = models.CharField(max_length=20, choices=ACTION_TYPES,default="hello")
    button_name = models.CharField(max_length=255)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    website_url = models.URLField(blank=True, null=True)
   
    uploaded_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.email,self.template_id}'

    
