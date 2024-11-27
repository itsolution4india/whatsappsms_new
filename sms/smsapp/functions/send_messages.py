from ..fastapidata import send_api
from ..models import ReportInfo, ScheduledMessage, CustomUser, CoinsHistory
from django.utils import timezone
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)

def schedule_subtract_coins(user, final_count, category):
    try:
        data = CustomUser.objects.get(email=user)
        if user is None or data.coins is None:
            logger.error("User or user coins not found.")
            return
        final_coins = final_count
        if data.coins >= final_coins:
            if category == "MARKETING":
                data.marketing_coins -= final_coins
                data.save()
            elif category == 'AUTHENTICATION' or category == 'UTILITY':
                data.authentication_coins -= final_coins
                data.save()
            coins_history = CoinsHistory(user=user, type='credit', number_of_coins=final_coins, reason=f"coins deducted towards {category}")
            coins_history.save()
            logger.info(f"Message sent successfully. Deducted {final_coins} coins from your account. Remaining balance: {data.coins}")
        else:
            logger.error("Insufficient coins to proceed.")
    except CustomUser.DoesNotExist:
        logger.error(f"User with email {user} does not exist.")
    except Exception as e:
        logger.error(f"Error while subtracting coins for user {user}: {str(e)}")

def subtract_coins(request, final_count, category):
    user = request.user
    if user is None or user.coins is None:
        messages.error(request, "User or user coins not found.")
        logger.error("User or user coins not found.")
        return
    final_coins = final_count
    if user.coins >= final_coins:
        if category == "MARKETING":
            user.marketing_coins -= final_coins
            user.save()
        elif category == 'AUTHENTICATION' or category == 'UTILITY':
            user.authentication_coins -= final_coins
            user.save()
        coins_history = CoinsHistory(user=user, type='credit', number_of_coins=final_coins, reason=f"coins deducted towards {category}")
        coins_history.save()
        messages.success(request, f"Message sent successfully. Deducted {final_coins} coins from your account.")
    else:
        logger.error("Insufficient coins to proceed.")
        messages.error(request, "You don't have enough coins to proceed.")

def display_phonenumber_id(request):
    phonenumber_id = request.user.phone_number_id
    return phonenumber_id

def display_whatsapp_id(request):
    whatsapp_id = request.user.whatsapp_business_account_id
    return whatsapp_id

def send_messages(current_user, token, phone_id, campaign_list, template_name, media_id, all_contact, contact_list, campaign_title, request, submitted_variables):
    try:
        logger.info(f"Sending messages for user: {current_user}, campaign title: {campaign_title}")
        for campaign in campaign_list:
            if campaign['template_name'] == template_name:
                language = campaign['template_language']
                media_type = campaign['media_type']
                category = campaign['category']

                money_data = len(all_contact) + 0 * len(all_contact)
                logger.info(f"Calculated money data for sending messages: {money_data}")

                if request:
                    subtract_coins(request, money_data, category)
                else:
                    schedule_subtract_coins(current_user, money_data, category)
                media_type = "OTP" if category == "AUTHENTICATION" else media_type
                send_api(token, phone_id, template_name, language, media_type, media_id, contact_list, submitted_variables)

        formatted_numbers = []
        for number in all_contact:
            if number.startswith("+91"):
                formatted_numbers.append("91" + number[3:])
            elif number.startswith("+977"):
                formatted_numbers.append("977" + number)
            elif number.startswith("+1"):
                formatted_numbers.append("1" + number)
            elif number.startswith("+61"):
                formatted_numbers.append("61" + number)
            else:
                formatted_numbers.append(number)

        phone_numbers_string = ",".join(formatted_numbers)

        ReportInfo.objects.create(
            email=str(current_user),
            campaign_title=campaign_title,
            contact_list=phone_numbers_string,
            message_date=timezone.now(),
            message_delivery=len(all_contact),
            template_name=template_name
        )
        logger.info(f"Messages sent successfully for campaign: {campaign_title}, user: {current_user}")
    except Exception as e:
        logger.error(f"Error in sending messages: {str(e)}")

def save_schedule_messages(current_user, template_name, media_id, all_contact, contact_list, campaign_title, schedule_date, schedule_time, submitted_variables):
    try:
        data = ScheduledMessage(
            current_user=current_user,
            template_name=template_name,
            media_id=media_id,
            all_contact=all_contact,
            contact_list=contact_list,
            campaign_title=campaign_title,
            schedule_date=schedule_date,
            schedule_time=schedule_time,
            submitted_variables=submitted_variables
        )
        data.save()
        logger.info(f"Scheduled message saved for campaign: {campaign_title}, user: {current_user}")
    except Exception as e:
        logger.error(f"Error in saving scheduled messages: {str(e)}")
