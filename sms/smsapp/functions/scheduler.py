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
from .meta_apis import send_message
from ..utils import logger
import ast
import json

scheduler = None
lock_file = os.path.join(settings.BASE_DIR, "scheduler.lock")


def run_scheduled_message(message_id):
    from django.db import close_old_connections
    
    # Close connections at the start
    close_old_connections()
    
    logger.info(f"Executing message send for ID: {message_id} at {timezone.now()}")
    try:
        # Use shorter lock duration
        with FileLock(lock_file, timeout=30):  # 30 second timeout on lock acquisition
            try:
                # Use a shorter transaction
                with transaction.atomic(using='default', savepoint=False):
                    try:
                        message = ScheduledMessage.objects.select_for_update(nowait=True).get(id=message_id)
                        if message.is_sent:
                            logger.info(f"Message {message_id} has already been sent. Skipping.")
                            return
                            
                        # Extract data inside the transaction
                        current_user = message.current_user
                        template_name = message.template_name
                        media_id = message.media_id
                        contact_list = message.contact_list
                        all_contact = message.all_contact
                        campaign_title = message.campaign_title
                        admin_schedule = message.admin_schedule
                        submitted_variables = message.submitted_variables
                        
                    except ScheduledMessage.DoesNotExist:
                        logger.error(f"Scheduled message with id {message_id} not found")
                        return
                
                # Perform app info fetch outside transaction
                app_info = CustomUser.get_app_info_by_email(current_user)
                user_data = CustomUser.objects.get(email=current_user)
                
                # Process data outside transaction
                if isinstance(submitted_variables, str):
                    try:
                        submitted_variables = json.loads(submitted_variables)
                    except json.JSONDecodeError:
                        submitted_variables = ast.literal_eval(submitted_variables)
                
                # Fetch templates outside transaction
                campaign_list = fetch_templates(user_data.whatsapp_business_account_id, app_info['token']) or []
                
                # Perform sending outside transaction
                if admin_schedule:
                    # Admin sending logic
                    language = None
                    media_type = None
                    for campaign in campaign_list:
                        if campaign['template_name'] == template_name:
                            language = campaign['template_language']
                            media_type = campaign['media_type']
                            
                    contact_list_eval = ast.literal_eval(contact_list)
                    for contact in contact_list_eval:
                        result = send_message(
                            app_info['token'], 
                            user_data.phone_number_id, 
                            template_name, 
                            language, 
                            media_type, 
                            media_id, 
                            contact, 
                            submitted_variables, 
                            None
                        )
                    
                else:
                    # Regular sending
                    send_messages(
                        current_user,
                        app_info['token'],
                        user_data.phone_number_id,
                        campaign_list,
                        template_name,
                        media_id,
                        ast.literal_eval(all_contact),
                        ast.literal_eval(contact_list),
                        campaign_title,
                        request=None,
                        submitted_variables=submitted_variables
                    )
                
                # Update message status in a separate transaction
                with transaction.atomic():
                    message = ScheduledMessage.objects.select_for_update().get(id=message_id)
                    message.is_sent = True if not admin_schedule else False
                    message.save()
                    
                logger.info(f"Message {message_id} processed successfully.")
                
            except Exception as e:
                logger.error(f"Error in run_scheduled_message: {str(e)}", exc_info=True)
    finally:
        # Always close connections when done
        close_old_connections()

def schedule_messages():
    from django.db import close_old_connections
    
    try:
        with FileLock(lock_file):
            india_timezone = pytz_timezone('Asia/Kolkata')
            now = timezone.now().astimezone(india_timezone)
            
            # Define batch size for processing
            BATCH_SIZE = 100
            
            # Get total count after setting 'now'
            total_messages = ScheduledMessage.objects.filter(
                schedule_date__gte=now.date(), 
                is_sent=False
            ).count()
            
            # Use shorter transaction to get the data
            with transaction.atomic():
                schedule_list = ScheduledMessage.objects.filter(
                    schedule_date__gte=now.date(), 
                    is_sent=False
                )
                schedule_list = list(schedule_list)  # Materialize query inside transaction
                
            # Process outside of transaction to avoid long locks
            existing_jobs = {job.id for job in scheduler.get_jobs()}
            
            # Process in batches if there are many messages
            for i in range(0, len(schedule_list), BATCH_SIZE):
                batch = schedule_list[i:i+BATCH_SIZE]
                
                for schedule in batch:
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
    finally:
        # Always close connections when done
        close_old_connections()


@receiver(post_save, sender=ScheduledMessage)
def handle_schedule_update(sender, instance, created, **kwargs):
    logger.info("handle_schedule_update function called")
    if created or not instance.is_sent:
        transaction.on_commit(schedule_messages)


def start_scheduler():
    global scheduler
    from django.db import close_old_connections

    if scheduler is None:
        scheduler = BackgroundScheduler(timezone=pytz_timezone('Asia/Kolkata'))
        def safe_schedule_messages():
            try:
                schedule_messages()
            finally:
                close_old_connections()
                
        scheduler.add_job(safe_schedule_messages, 'interval', minutes=45)
        
        try:
            scheduler.start()
            logger.info("Scheduler started successfully")
        except Exception as e:
            logger.error(f"Error starting the scheduler: {str(e)}")

