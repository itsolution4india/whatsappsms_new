from django.apps import AppConfig
import os
import logging

logger = logging.getLogger(__name__)

class SmsappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'smsapp'

    def ready(self):
        if os.environ.get('DJANGO_SETTINGS_MODULE') == 'sms.settings':
            try:
                from .functions.scheduler import start_scheduler
                start_scheduler()
                logger.info("Scheduler initialized in ready method.")
            except Exception as e:
                logger.error(f"Error while starting the scheduler: {str(e)}")
