import os
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
from django.utils import timezone
from pytz import timezone as pytz_timezone
from datetime import datetime
import ast
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from filelock import FileLock
from django.conf import settings
from ..models import ScheduledMessage, CustomUser
from .send_messages import send_messages, send_admin_testing_messages
from .template_msg import fetch_templates
import logging
from ..utils import logger
import ast
import json

scheduler = None
lock_file = os.path.join(settings.BASE_DIR, "scheduler.lock")


def run_scheduled_message(message_id):
    logger.info(f"Executing message send for ID: {message_id} at {timezone.now()}")
    with FileLock(lock_file):
        with transaction.atomic():
            try:
                message = ScheduledMessage.objects.select_for_update().get(id=message_id)
                if message.is_sent:
                    logger.info(f"Message {message_id} has already been sent. Skipping.")
                    return

                app_info = CustomUser.get_app_info_by_email(message.current_user)
                user_data = CustomUser.objects.get(email=message.current_user)
                
                # Fetch campaign list and ensure it's not None
                campaign_list = fetch_templates(user_data.whatsapp_business_account_id, app_info['token']) or []
                if isinstance(message.submitted_variables, str):
                    try:
                        # Attempt to parse as JSON or Python list
                        submitted_variables = json.loads(message.submitted_variables)
                    except json.JSONDecodeError:
                        submitted_variables = ast.literal_eval(message.submitted_variables)
                else:
                    submitted_variables = message.submitted_variables
                    
                logger.info(f"send_messages function called for message {message_id}")
                if message.admin_schedule:
                    send_admin_testing_messages(
                        message.current_user,
                        app_info['token'],
                        user_data.phone_number_id,
                        campaign_list,
                        message.template_name,
                        message.media_id,
                        ast.literal_eval(message.all_contact),
                        ast.literal_eval(message.contact_list),
                        message.campaign_title,
                        request=None,
                        submitted_variables=submitted_variables
                    )
                    message.is_sent = False
                    logger.info(f"Admin testing message {message_id} sent successfully.")
                else:
                    send_messages(
                        message.current_user,
                        app_info['token'],
                        user_data.phone_number_id,
                        campaign_list,
                        message.template_name,
                        message.media_id,
                        ast.literal_eval(message.all_contact),
                        ast.literal_eval(message.contact_list),
                        message.campaign_title,
                        request=None,
                        submitted_variables=submitted_variables
                    )
                    logger.info(f"Message {message_id} sent successfully.")
                    message.is_sent = True
                message.save()
                logger.info(f"Message {message_id} sent successfully.")
            except ScheduledMessage.DoesNotExist:
                logger.error(f"Scheduled message with id {message_id} not found")


def schedule_messages():
    with FileLock(lock_file):
        india_timezone = pytz_timezone('Asia/Kolkata')
        now = timezone.now().astimezone(india_timezone)

        schedule_list = ScheduledMessage.objects.filter(schedule_date__gte=now.date(), is_sent=False)
        existing_jobs = {job.id for job in scheduler.get_jobs()}
        
        for schedule in schedule_list:
            if schedule.schedule_type == ScheduledMessage.DAILY:
                schedule_date = now.date()
            else:
                schedule_date = datetime.strptime(schedule.schedule_date, "%Y-%m-%d").date()

            scheduled_datetime = datetime.combine(
                schedule_date,
                datetime.strptime(schedule.schedule_time, "%H:%M:%S").time()
            )
            scheduled_datetime = india_timezone.localize(scheduled_datetime)

            if scheduled_datetime > now:
                job_id = f"message_{schedule.id}"
                if job_id not in existing_jobs:
                    logger.info(f"Adding job: {job_id} with scheduled time: {scheduled_datetime}")
                    scheduler.add_job(
                        run_scheduled_message,
                        'date',
                        run_date=scheduled_datetime,
                        args=[schedule.id],
                        id=job_id,
                        replace_existing=True,
                        max_instances=1
                    )


@receiver(post_save, sender=ScheduledMessage)
def handle_schedule_update(sender, instance, created, **kwargs):
    logger.info("handle_schedule_update function called")
    if created or not instance.is_sent:
        schedule_messages()


def start_scheduler():
    global scheduler

    if scheduler is None:
        scheduler = BackgroundScheduler(timezone=pytz_timezone('Asia/Kolkata'))
        scheduler.add_job(schedule_messages, 'interval', minutes=45)
        try:
            scheduler.start()
        except Exception as e:
            logger.error(f"Error starting the scheduler: {str(e)}")

