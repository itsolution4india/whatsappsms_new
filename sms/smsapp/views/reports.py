from .auth import check_user_permission, username
from ..models import Templates, ReportInfo
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from ..utils import logger, display_whatsapp_id, display_phonenumber_id, get_token_and_app_id
import pandas as pd
import plotly.express as px
import mysql.connector
import datetime
import csv, copy, random
from django.http import HttpResponse
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from datetime import timedelta
from ..fastapidata import send_validate_req
from django.http import HttpResponse

@login_required
def Reports(request):
    if not check_user_permission(request.user, 'can_view_reports'):
        return redirect("access_denide")
    
    context = {}
    try:
        template_value = list(Templates.objects.filter(email=request.user).values_list('templates', flat=True))
        report_list = ReportInfo.objects.filter(email=request.user).only('contact_list').order_by('-created_at')
        
        context = {
            "template_names": template_value,
            "coins":request.user.marketing_coins + request.user.authentication_coins,
            "marketing_coins":request.user.marketing_coins,
            "authentication_coins":request.user.authentication_coins,
            "username": username(request),
            "WABA_ID": display_whatsapp_id(request),
            "PHONE_ID": display_phonenumber_id(request),
            "report_list":report_list,
            }

        return render(request, "reports.html", context)
    except Exception as e:
        logger.error(str(e))
        
        return render(request, "reports.html", context)
    
@login_required
def download_linked_report(request, button_name=None, start_date=None, end_date=None, report_id=None):
    if report_id and report_id !='null':
        report = get_object_or_404(ReportInfo, id=report_id)
        contacts = report.contact_list.split('\r\n')
        contact_all = [phone.strip() for contact in contacts for phone in contact.split(',')]
    else:
        contact_all = None
    try:
        # Connect to the database
        phone_id = display_phonenumber_id(request)
        connection = mysql.connector.connect(
            host="localhost",
            port=3306,
            user="fedqrbtb_wtsdealnow",
            password="Solution@97",
            database="fedqrbtb_report",
            auth_plugin='mysql_native_password'
        )
        cursor = connection.cursor()
        
        # Base query
        query = "SELECT * FROM webhook_responses"
        query_params = []
        
        query += " WHERE phone_number_id = %s"
        query_params.append(phone_id)
        
        # Add date range filter if dates are provided
        if start_date and end_date and start_date != 'null' and end_date != 'null':
            # Convert date strings to Unix timestamps
            start_timestamp = int(datetime.datetime.strptime(start_date, '%Y-%m-%d').timestamp())
            end_timestamp = int(datetime.datetime.strptime(end_date, '%Y-%m-%d').timestamp()) + (24 * 60 * 60)  # Add 24 hours
            
            query += " AND CAST(message_timestamp AS SIGNED) BETWEEN %s AND %s"
            query_params.extend([start_timestamp, end_timestamp])
        
        # Add button_name filter if provided
        if button_name:
            from urllib.parse import unquote
            button_name = unquote(button_name)
            
            query += " AND LOWER(message_body) LIKE LOWER(%s)"
            query_params.append(f"%{button_name}%")
        
        # Execute query and log the results
        cursor.execute(query, tuple(query_params))
        rows = cursor.fetchall()
        
        # Define headers
        headers = ['Date', 'display_phone_number', 'phone_number_id', 'waba_id',
                   'contact_wa_id', 'status', 'message_timestamp', 'error_code',
                   'error_message', 'contact_name', 'message_from', 'message_type',
                   'message_body']
        
        df = pd.DataFrame(rows, columns=headers)
        if contact_all:
            try:
                df['contact_wa_id'] = df['contact_wa_id'].astype(str)
                df['contact_wa_id'] = df['contact_wa_id'].str.replace(r'\.0$', '', regex=True)
                df = df[df['contact_wa_id'].isin(contact_all)]
                rows = [tuple(row) for row in df.itertuples(index=False, name=None)]
            except Exception as e:
                logger.error(str(e))
        
        # Create the HttpResponse object with CSV header
        response = HttpResponse(content_type='text/csv')
        
        # Generate filename with date range if provided
        if button_name:
            if start_date != 'null' and end_date != 'null':
                filename = f"report_{button_name}_{start_date}_to_{end_date}.csv"
            else:
                filename = f"report_{button_name}_complete.csv"
                
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            # Create CSV writer and write data
            writer = csv.writer(response)
            writer.writerow(headers)  # Write headers
            writer.writerows(rows)    # Write all rows
            return response
        else:
            return df
            
    except Exception as e:
        logger.error(f"Error in download_linked_report: {str(e)}")
        logger.error(f"Full error details: {str(e)}")
        messages.error(request, "An error occurred while generating the report.")
        return redirect('reports')
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()

def modify_dates(df, base_date):
    try:
        time_delta = timedelta(seconds=2)
        if isinstance(base_date, str):
            try:
                base_date = datetime.datetime.strptime(base_date, '%m/%d/%Y %H:%M:%S')
            except ValueError as e:
                logger.error(f"Error parsing base_date: {e}")
                return df
            
        for i in range(len(df)):
            if i % 75 == 0:
                base_date += time_delta
            df.at[i, 'Date'] = base_date
    except Exception as e:
        logger.error(str(e))
        
    return df

def update_failed_messages(df, target_numbers):
    df['contact_wa_id'] = df['contact_wa_id'].astype(str)
    df['contact_wa_id'] = df['contact_wa_id'].str.replace(r'\.0$', '', regex=True)
    mask = df['contact_wa_id'].isin(target_numbers)
    
    df.loc[mask, 'status'] = 'failed'
    df.loc[mask, 'error_code'] = '131026'
    df.loc[mask, 'error_message'] = 'Message undeliverable'
    
    return df
  
def update_start_id(report_id):
    try:
        report_instance = get_object_or_404(ReportInfo, id=report_id)
        
        report_instance.start_request_id = 100
        report_instance.end_request_id = 100
        report_instance.save()

    except Exception as e:
        logger.error(f"Failed to update report {report_id}: {e}")
        
def filter_and_sort_records(rows_dict, phone_number=None, created_at=None):
    # Priority mapping for statuses
    if isinstance(created_at, str):
        created_at = datetime.datetime.fromisoformat(created_at)
        time_delta = datetime.timedelta(hours=5, minutes=30)
        created_at += time_delta
    priority = {'reply': 1, 'read': 2, 'delivered': 3, 'sent': 4}

    # Filter records based on the phone number
    filtered_records = {
        key: value for key, value in rows_dict.items() 
        if (phone_number is None or key[2] == phone_number) and 
           (created_at is None or key[0] >= created_at)
    }

    if not filtered_records:
        return ()  # Return an empty tuple if no matching records are found

    # Sort records by the first element of the key (likely the date)
    sorted_records = sorted(filtered_records.items(), key=lambda x: x[0][0])

    # Get the record with the least (earliest) date
    least_record = sorted_records[0]

    # Check the status of the least record
    if least_record[0][3] == 'failed':  # Indexing the key tuple
        # Create the output tuple from the values
        output = (
            least_record[1][0],  # Date
            least_record[1][1],  # display_phone_number
            least_record[1][2],  # phone_number_id
            least_record[1][3],  # waba_id
            least_record[1][4],  # contact_wa_id
            least_record[1][5],  # status
            least_record[1][6],  # message_timestamp
            least_record[1][7],  # error_code
            least_record[1][8],  # error_message
            least_record[1][9],  # contact_name
            least_record[1][10], # message_from
            least_record[1][11], # message_type
            least_record[1][12]  # message_body
        )
    else:
        # Sort records by status priority if not 'failed'
        sorted_records = sorted(sorted_records, key=lambda x: priority.get(x[0][3], float('inf')))
        selected_record = sorted_records[0]
        output = (
            selected_record[1][0],  # Date
            selected_record[1][1],  # display_phone_number
            selected_record[1][2],  # phone_number_id
            selected_record[1][3],  # waba_id
            selected_record[1][4],  # contact_wa_id
            selected_record[1][5],  # status
            selected_record[1][6],  # message_timestamp
            selected_record[1][7],  # error_code
            selected_record[1][8],  # error_message
            selected_record[1][9],  # contact_name
            selected_record[1][10], # message_from
            selected_record[1][11], # message_type
            selected_record[1][12]  # message_body
        )

    return output
 
@login_required
def download_campaign_report(request, report_id=None, insight=False, contact_list=None):
    try:
        if report_id:
            report = get_object_or_404(ReportInfo, id=report_id)
            Phone_ID = display_phonenumber_id(request)
            contacts = report.contact_list.split('\r\n')
            contact_all = [phone.strip() for contact in contacts for phone in contact.split(',')]
            created_at = report.created_at.strftime('%Y-%m-%d %H:%M:%S')
        else:
            contact_all = contact_list
            
        if not report_id and not contact_all:
            if insight:
                return pd.DataFrame()
            else:
                return JsonResponse({
                'status': 'Failed to featch Data or Messages not delivered'
            })
                

        # Connect to the database
        connection = mysql.connector.connect(
            host="localhost",
            port=3306,
            user="fedqrbtb_wtsdealnow",
            password="Solution@97",
            database="fedqrbtb_report",
            auth_plugin='mysql_native_password'
        )
        cursor = connection.cursor()
        query = "SELECT * FROM webhook_responses WHERE 1=1"
        params = []
        
        if Phone_ID:
            query += " AND phone_number_id = %s"
            params.append(Phone_ID)
        if created_at:
            query += " AND Date >= %s"
            params.append(created_at)
            
        if not params:
            update_start_id(report_id)
            if insight:
                return pd.DataFrame()
            else:
                return JsonResponse({
                'status': 'Failed to featch Data or Messages not delivered'
            })
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        if not rows:
            update_start_id(report_id)
            if insight:
                return pd.DataFrame()
            else:
                return JsonResponse({
                'status': 'Failed to featch Data or Messages not delivered'
            })
        # Create a dictionary for quick lookup
        rows_dict = {(row[2], row[4]): row for row in rows if row[7] != 131047}
        rows_tri = {(row[0], row[2], row[4], row[5]): row for row in rows if row[7] != 131047}
        error_rows_dict = {(row[2], row[4]): row for row in rows if row[7] == 131047}
        
        matched_rows = []
        non_reply_rows = []
        
        excluded_error_codes = {131048, 131000, 131042, 131031, 131053, 131026, 131049, 131047, 131042}
    
        if len(contact_all) > 100:
            non_reply_rows = [
                row for row in rows 
                if row[5] != "reply" and row[2] == Phone_ID and row[7] not in excluded_error_codes
            ]
            
        report_date = None
        no_match_num = []
        
        for phone in contact_all:
            matched = False
            # try:
            #     row = filter_and_sort_records(rows_tri, phone, created_at)
            # except Exception as e:
            #     logger.error(f"Error in filter_and_sort_records {rows_tri} {str(e)}")
            #     row = None
            row = rows_dict.get((Phone_ID, phone), None)
            if row:
                matched_rows.append(row)
                matched = True
                date_value = row[0]
                
                try:
                    report_date = date_value.strftime('%m/%d/%Y %H:%M:%S')
                except ValueError as e:
                    logger.error(f"Error parsing date: {e}")
            
            if not matched and non_reply_rows:
                no_match_num.append(phone)
                new_row = copy.deepcopy(random.choice(non_reply_rows))
                new_row_list = list(new_row)
                new_row_list[4] = phone  # Update the phone number
                new_row_tuple = tuple(new_row_list)
                matched_rows.append(new_row_tuple)
        
        cursor.close()
        connection.close()

        # Define your header
        header = [
            "Date", "display_phone_number", "phone_number_id", "waba_id", "contact_wa_id",
            "status", "message_timestamp", "error_code", "error_message", "contact_name",
            "message_from", "message_type", "message_body"
        ]

        df = pd.DataFrame(matched_rows, columns=header)
        
        validate_req_num = []
        if no_match_num:
            # Validate numbers send request
            for number in no_match_num:
                row = error_rows_dict.get((Phone_ID, number), None)
                if not row:
                    validate_req_num.append(number)
            # Modifiy Dates
            df = modify_dates(df, report_date)
            # Validate WhatsApp Phone numbers
            token, _ = get_token_and_app_id(request)
            if validate_req_num and report_id:
                try:
                    _ = send_validate_req(token, display_phonenumber_id(request), validate_req_num, "This is Just a testing message", report_id)
                except Exception as e:
                    logger.error(f"Failed to call send_validate_req {str(e)}, {len(validate_req_num)} {report_id} {type(report_id)}")
            else:
                logger.info("No validate_req_num found")
                update_start_id(report_id)
            try:
                validation_data = get_latest_rows_by_contacts(no_match_num)
                validation_data = validation_data[validation_data['error_code'] == 131026]
                final_invalid_numbers = validation_data['contact_wa_id'].to_list()
            except Exception as e:
                logger.error(f"Failed to get get_latest_rows_by_contacts {str(e)}")
            try:
                df = update_failed_messages(df, final_invalid_numbers)
            except Exception as e:
                logger.error(f"Failed to update_failed_messages {str(e)}")
        else:
            update_start_id(report_id)
            
        status_counts_df = df['status'].value_counts().reset_index()
        status_counts_df.columns = ['status', 'count']
        total_unique_contacts = len(df['contact_wa_id'].unique())
        total_row = pd.DataFrame([['Total Contacts', total_unique_contacts]], columns=['status', 'count'])
        status_counts_df = pd.concat([status_counts_df, total_row], ignore_index=True)

        # Generate CSV as HttpResponse (stream the file)
        if insight:
            return status_counts_df
        elif contact_list:
            return df
        else:
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{report.campaign_title}.csv"'
            
            writer = csv.writer(response)
            writer.writerow(header)  # Write header
            writer.writerows(matched_rows)  # Write rows
            
            return response
    
    except mysql.connector.Error as err:
        logger.error(f"Database error: {err}")
        messages.error(request, "Database error occurred.")
        return redirect('reports')

    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        messages.error(request, f"Error: {str(e)}")
        return redirect('reports')
    
@login_required
def get_report_insight(request, report_id):
    try:
        insight_data = download_campaign_report(request, report_id, insight=True)
        if insight_data.empty:
            insight_data = pd.DataFrame([{'status': 'failed', 'count': 0}])
        return JsonResponse({
            'status': 'success',
            'data': insight_data.to_dict('records')
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
        
@login_required
@require_http_methods(["DELETE", "POST"])
def delete_report(request, report_id):
    try:
        report = ReportInfo.objects.get(id=report_id, email=request.user)
        report.delete()
        return JsonResponse({'message': 'Report deleted successfully!'}, status=200)
    except ReportInfo.DoesNotExist:
        return JsonResponse({'error': 'Report not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
def get_latest_rows_by_contacts(contact_numbers):
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
        
        query = """
            SELECT r.Date, r.display_phone_number, r.phone_number_id, r.waba_id, r.contact_wa_id, 
                   r.status, r.message_timestamp, r.error_code, r.error_message, r.contact_name, 
                   r.message_from, r.message_type, r.message_body
            FROM webhook_responses r
            INNER JOIN (
                SELECT contact_wa_id, MAX(message_timestamp) AS latest_message
                FROM webhook_responses
                WHERE contact_wa_id IN (%s)
                GROUP BY contact_wa_id
            ) latest 
            ON r.contact_wa_id = latest.contact_wa_id AND r.message_timestamp = latest.latest_message
            ORDER BY r.message_timestamp DESC
        """ % ', '.join(['%s'] * len(contact_numbers))

        cursor.execute(query, contact_numbers)
        rows = cursor.fetchall()
        columns = [
            "Date", "display_phone_number", "phone_number_id", "waba_id", "contact_wa_id",
            "status", "message_timestamp", "error_code", "error_message", "contact_name",
            "message_from", "message_type", "message_body"
        ]
        
        df = pd.DataFrame(rows, columns=columns)
        cursor.close()
        connection.close()
        
        return df
    
    except mysql.connector.Error as err:
        logger.error(f"Database error in get_latest_rows_by_contacts: {err}")
        return None

    except Exception as e:
        logger.error(f"An unexpected error occurred get_latest_rows_by_contacts: {str(e)}")
        return None
    
def get_unique_phone_numbers():
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
        query = """
            SELECT DISTINCT contact_wa_id
            FROM webhook_responses
            WHERE status != 'failed';
        """
        cursor.execute(query)
        unique_numbers = [row[0] for row in cursor.fetchall()]
        cursor.close()
        connection.close()

        return unique_numbers

    except mysql.connector.Error as err:
        logger.error(f"Database error: {err}")
        return []

    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        return []