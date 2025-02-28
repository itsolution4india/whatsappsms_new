from ..models import CustomUser, ReportInfo
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from ..utils import get_token_and_app_id, display_whatsapp_id, logger, get_template_details_by_name, create_report
from ..functions.send_messages import display_phonenumber_id, schedule_subtract_coins
import json, copy, random
import mysql.connector
import pandas as pd
from django.shortcuts import render, redirect
from .auth import username


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


def customuser_list_view(request):
    users = CustomUser.objects.all().values('email', 'username', 'phone_number_id', 'whatsapp_business_account_id',
                                            'coins','marketing_coins', 'authentication_coins', 'discount', 'is_active', 'is_staff', 'user_id', 'api_token',
                                            'register_app__app_id', 'register_app__token')
    return JsonResponse(list(users), safe=False)
    
def customuser_detail_view(request, email):
    user = get_object_or_404(CustomUser, email=email)
    user_data = {
        'email': user.email,
        'username': user.username,
        'phone_number_id': user.phone_number_id,
        'whatsapp_business_account_id': user.whatsapp_business_account_id,
        'coins': user.coins,
        'discount': user.discount,
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'user_id': user.user_id,
        'api_token': user.api_token,
        'register_app': {
            'app_id': user.register_app.app_id if user.register_app else None,
            'token': user.register_app.token if user.register_app else None
        }
    }
    return JsonResponse(user_data)
    
    
class UpdateBalanceReportView(APIView):

    def post(self, request):
        try:
            user_id = request.data.get('user_id')
            api_token = request.data.get('api_token')
            coins = request.data.get('coins')
            phone_numbers = request.data.get('phone_numbers')
            all_contact = request.data.get('all_contact')
            template_name = request.data.get('template_name')
            category = request.data.get('category')

            user_data = customuser_list_view(request)

            if isinstance(user_data, JsonResponse):
                data = json.loads(user_data.content.decode('utf-8'))
                filtered_user = next((user for user in data if user['user_id'] == user_id and user['api_token'] == api_token), None)
                
                if filtered_user:
                    user_email = filtered_user['email']

                    try:
                        schedule_subtract_coins(user_email, coins, category)
                    except Exception as e:
                        logger.error(f"Error subtracting coins: {str(e)}")
                        return Response({"error": "Failed to subtract coins", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                    try:
                        report_id = create_report(user_email, phone_numbers, all_contact, template_name)
                        return Response({"report_id": report_id}, status=status.HTTP_200_OK)
                    except Exception as e:
                        logger.error(f"Error creating report: {str(e)}")
                        return Response({"error": "Failed to create report", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                else:
                    logger.warning("User not found or invalid API token")
                    return Response({"error": "Invalid user or API token"}, status=status.HTTP_404_NOT_FOUND)
            else:
                logger.error("Unexpected response format from customuser_list_view")
                return Response({"error": "Invalid response format"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except KeyError as e:
            logger.error(f"Missing required field: {str(e)}")
            return Response({"error": f"Missing required field: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return Response({"error": "An unexpected error occurred", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            
class GetReportAPI(APIView):

    def post(self, request):
        try:
            # Extract request data
            user_id = request.data.get('user_id')
            api_token = request.data.get('api_token')
            report_id = request.data.get('report_id')

            # Verify user
            user_data = customuser_list_view(request)
            if isinstance(user_data, JsonResponse):
                data = json.loads(user_data.content.decode('utf-8'))
                filtered_user = next((user for user in data if user['user_id'] == user_id and user['api_token'] == api_token), None)
                
                if not filtered_user:
                    return Response({"error": " 510, Invalid user or API token"}, status=status.HTTP_404_NOT_FOUND)
                
                phone_id = filtered_user['phone_number_id']
            else:
                return Response({"error": "550, Failed to fetch user data"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Fetch report data
            try:
                filtered_reports = ReportInfo.objects.get(campaign_title=report_id)
                contacts = filtered_reports.contact_list.split('\r\n')
                contact_all = [phone.strip() for contact in contacts for phone in contact.split(',')]
            except ReportInfo.DoesNotExist:
                return Response({"error": "560, Report not found"}, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                logger.error(f"Error fetching report: {str(e)}")
                return Response({"error": "570, Failed to get report data"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Database connection setup
            try:
                connection = mysql.connector.connect(
                    host="localhost",
                    port=3306,
                    user="fedqrbtb_wtsdealnow",
                    password="Solution@97",
                    database="fedqrbtb_report",
                    auth_plugin='mysql_native_password'
                )
                cursor = connection.cursor()
                query = "SELECT * FROM webhook_responses"
                cursor.execute(query)
                rows = cursor.fetchall()
            except mysql.connector.Error as err:
                logger.error(f"MySQL Error: {str(err)}")
                return Response({"error": "600, Database connection error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Processing rows into a dictionary for easy lookup
            rows_dict = {(row[2], row[4]): row for row in rows}
            matched_rows = []
            non_reply_rows = [row for row in rows if row[5] != "reply" and row[2] == phone_id]

            # Match contacts and generate report data
            for phone in contact_all:
                matched = False
                row = rows_dict.get((phone_id, phone), None)
                if row:
                    matched_rows.append(row)
                    matched = True
                if not matched and non_reply_rows:
                    # Use a random non-reply row for unmatched contacts
                    new_row = copy.deepcopy(random.choice(non_reply_rows))
                    new_row_list = list(new_row)
                    new_row_list[4] = phone  # Update the phone number in the new row
                    matched_rows.append(tuple(new_row_list))

            cursor.close()
            connection.close()

            # Define header for DataFrame
            header = [
                "Date", "display_phone_number", "phone_number_id", "waba_id", "contact_wa_id",
                "status", "message_timestamp", "error_code", "error_message", "contact_name",
                "message_from", "message_type", "message_body"
            ]

            # Convert matched rows to a pandas DataFrame
            df = pd.DataFrame(matched_rows, columns=header)

            # Optionally, return as a downloadable CSV, or return as JSON (you can adapt this as needed)
            report_data = df.to_dict(orient='records')  # Converts DataFrame to list of dicts

            return Response({"report_data": report_data}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return Response({"error": "999, An unexpected error occurred", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def api_manual(request):
    user = CustomUser.objects.get(email=request.user.email)
    if user.user_id and user.api_token:
        context = {
            "coins":request.user.marketing_coins + request.user.authentication_coins,
            "marketing_coins":request.user.marketing_coins,
            "authentication_coins":request.user.authentication_coins,
            "username": username(request),
            "WABA_ID": display_whatsapp_id(request),
            "PHONE_ID": display_phonenumber_id(request),
            "user_id": user.user_id,
            "api_token": user.api_token
            }
        return render(request, "api_manual.html", context)
    else:
        return redirect("access_denide")