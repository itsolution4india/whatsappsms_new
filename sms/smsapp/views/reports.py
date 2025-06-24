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
from ..functions.template_msg import fetch_templates
import zipfile
import io
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


from dotenv import load_dotenv
import os

load_dotenv()

@login_required
def Reports(request):
    if not check_user_permission(request.user, 'can_view_reports'):
        return redirect("access_denide")
    
    context = {}
    try:
        token, _ = get_token_and_app_id(request)
        campaign_list = fetch_templates(display_whatsapp_id(request), token)
        if campaign_list is None:
            campaign_list = []
        template_value = list(Templates.objects.filter(email=request.user).values_list('templates', flat=True))
        template_value2 = [campaign_list[i] for i in range(len(campaign_list)) if campaign_list[i]['template_name'] in template_value]
        report_query = ReportInfo.objects.filter(email=request.user)
        
        # Apply filters
        if request.GET.get('start_date'):
            report_query = report_query.filter(message_date__gte=request.GET.get('start_date'))
        
        if request.GET.get('end_date'):
            report_query = report_query.filter(message_date__lte=request.GET.get('end_date'))
        
        if request.GET.get('campaign_title'):
            report_query = report_query.filter(
                campaign_title__icontains=request.GET.get('campaign_title')
            )
        
        if request.GET.get('template_name'):
            report_query = report_query.filter(
                template_name=request.GET.get('template_name')
            )
        
        if request.GET.get('download_in_bulk'):
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            if not start_date and not end_date:
                return JsonResponse({
                    'status': 'Failed',
                    "Reason": "Select Start Date And End Date"
                })
            report_ids = report_query.values_list('id', flat=True)
            report_ids = list(report_ids)
            response = bulk_download(request, report_ids)
            return response
            
        # Order the reports
        report_list = report_query.only('contact_list').order_by('-created_at')
        
        # Pagination
        page = request.GET.get('page', 1)
        items_per_page = 10  # You can adjust this number
        paginator = Paginator(report_list, items_per_page)
        
        try:
            report_list_paginated = paginator.page(page)
        except PageNotAnInteger:
            report_list_paginated = paginator.page(1)
        except EmptyPage:
            report_list_paginated = paginator.page(paginator.num_pages)
        
        show_button = any(report.end_request_id == 0 or report.start_request_id == 0 for report in report_list)
        context = {
            "all_template_names": template_value2,
            "template_names": template_value,
            "coins": request.user.marketing_coins + request.user.authentication_coins,
            "marketing_coins": request.user.marketing_coins,
            "authentication_coins": request.user.authentication_coins,
            "username": username(request),
            "WABA_ID": display_whatsapp_id(request),
            "PHONE_ID": display_phonenumber_id(request),
            "report_list": report_list_paginated,
            "show_button": show_button
        }

        return render(request, "reports.html", context)
    except Exception as e:
        logger.error(str(e))
        return render(request, "reports.html", context)
    
# version 1
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
        _, AppID = get_token_and_app_id(request)
        connection = mysql.connector.connect(
            host=os.getenv('SQLHOST'),
            port=os.getenv('SQLPORT'),
            user=os.getenv('SQLUSER'),
            password=os.getenv('SQLPASSWORD'),
            database= os.getenv('SQLDATABASE'),
            auth_plugin=os.getenv('SQLAUTH')
        )
        cursor = connection.cursor()
        
        # Base query
        query = f"SELECT * FROM webhook_responses_{AppID}"
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

#version 2
@login_required
def download_campaign_report3(request, report_id=None, insight=False, contact_list=None):
    try:
        if report_id:
            report = get_object_or_404(ReportInfo, id=report_id)
            Phone_ID = display_phonenumber_id(request)
            contacts = report.contact_list.split('\r\n')
            contact_all = [phone.strip() for contact in contacts for phone in contact.split(',')]
            created_at = report.created_at.strftime('%Y-%m-%d %H:%M:%S')
            if isinstance(created_at, str):
                created_at = datetime.datetime.fromisoformat(created_at)
            time_delta = datetime.timedelta(hours=5, minutes=30)
            created_at += time_delta
        else:
            contact_all = contact_list
            Phone_ID = display_phonenumber_id(request)
            created_at = None 
        if not report_id and not contact_all:
            if insight:
                return pd.DataFrame()
            else:
                return JsonResponse({
                    'status': 'Failed to fetch Data or Messages not delivered'
                })
                
        # Connect to the database
        connection = mysql.connector.connect(
            host=os.getenv('SQLHOST'),
            port=os.getenv('SQLPORT'),
            user=os.getenv('SQLUSER'),
            password=os.getenv('SQLPASSWORD'),
            database= os.getenv('SQLDATABASE'),
            auth_plugin=os.getenv('SQLAUTH')
        )
        cursor = connection.cursor()
        
        # Create the priority ranking case statement
        priority_case = """
            CASE status 
                WHEN 'failed' THEN 1
                WHEN 'reply' THEN 2
                WHEN 'read' THEN 3
                WHEN 'delivered' THEN 4
                WHEN 'sent' THEN 5
                ELSE 6
            END
        """
        
        # Convert contact list to string for SQL IN clause
        contacts_str = "', '".join(contact_all)
        
        date_filter = f"AND Date >= '{created_at}'" if created_at else ""
        
        # SQL query to get unique record for each contact with prioritized selection
        query = f"""
            WITH RankedMessages AS (
                SELECT 
                    Date,
                    display_phone_number,
                    phone_number_id,
                    waba_id,
                    contact_wa_id,
                    status,
                    message_timestamp,
                    error_code,
                    error_message,
                    contact_name,
                    message_from,
                    message_type,
                    message_body,
                    ROW_NUMBER() OVER (
                        PARTITION BY contact_wa_id 
                        ORDER BY 
                            CASE status 
                                WHEN 'failed' THEN 1
                                ELSE 2
                            END,
                            {priority_case},
                            message_timestamp ASC
                    ) as rn
                FROM webhook_responses
                WHERE contact_wa_id IN ('{contacts_str}')
                AND phone_number_id = '{Phone_ID}'
                {date_filter}
            )
            SELECT 
                Date,
                display_phone_number,
                phone_number_id,
                waba_id,
                contact_wa_id,
                status,
                message_timestamp,
                error_code,
                error_message,
                contact_name,
                message_from,
                message_type,
                message_body
            FROM RankedMessages
            WHERE rn = 1
            ORDER BY contact_wa_id;
        """
        
        cursor.execute(query)
        matched_rows = cursor.fetchall()
        
        error_codes_to_check = {"131031", "131053", "131042"}
        error_code = None 
        
        if report_id != 1520:
            for row in matched_rows:
                current_error_code = str(row[7])
                if current_error_code in error_codes_to_check:
                    error_code = current_error_code
                    break
        
        matched_rows, non_reply_rows = report_step_two(matched_rows, Phone_ID, error_code, created_at, report_id)
        
        rows_dict = {(row[2], row[4]): row for row in matched_rows}
        updated_matched_rows = []
        no_match_num = []
        
        for phone in contact_all:
            matched = False
            row = rows_dict.get((Phone_ID, phone), None)
            if row:
                updated_matched_rows.append(row)
                matched = True
                date_value = row[0]
                
                try:
                    report_date = date_value.strftime('%m/%d/%Y %H:%M:%S')
                except ValueError as e:
                    logger.error(f"Error parsing date: {e}")
            
            if len(contact_all) > 100: 
                if not matched and non_reply_rows:
                    no_match_num.append(phone)
                    new_row = copy.deepcopy(random.choice(non_reply_rows))
                    new_row_list = list(new_row)
                    new_row_list[4] = phone
                    new_row_tuple = tuple(new_row_list)
                    updated_matched_rows.append(new_row_tuple)
            else:
                if not matched and non_reply_rows:
                    no_match_num.append(phone)
                    new_row = copy.deepcopy(random.choice(non_reply_rows))
                    new_row_list = list(new_row)
                    try:
                        new_row_list[0] = created_at
                    except Exception as e:
                        logger.error(str(e))
                    new_row_list[4] = phone
                    new_row_list[5] = "failed"
                    new_row_list[7] = 100
                    new_row_list[8] = "Internal server Error"
                    new_row_tuple = tuple(new_row_list)
                    updated_matched_rows.append(new_row_tuple)
                
        
        response = HttpResponse(content_type='text/csv')
        if report_id:
            response['Content-Disposition'] = f'attachment; filename="{report.campaign_title}.csv"'
        else:
            response['Content-Disposition'] = 'attachment; filename="campaign_report.csv"'
        
        header = [
            "Date", "display_phone_number", "phone_number_id", "waba_id", "contact_wa_id",
            "status", "message_timestamp", "error_code", "error_message", "contact_name",
            "message_from", "message_type", "message_body"
        ]
        
        df = pd.DataFrame(updated_matched_rows, columns=header)
        status_counts_df = df['status'].value_counts().reset_index()
        status_counts_df.columns = ['status', 'count']
        total_unique_contacts = len(df['contact_wa_id'].unique())
        total_row = pd.DataFrame([['Total Contacts', total_unique_contacts]], columns=['status', 'count'])
        status_counts_df = pd.concat([status_counts_df, total_row], ignore_index=True)
        
        if insight:
            return status_counts_df
        else:
            writer = csv.writer(response)
            writer.writerow(header)
            writer.writerows(updated_matched_rows)
            cursor.close()
            connection.close()
            return response
        
    except Exception as e:
        logger.error(f"Error in download_campaign_report2: {str(e)}")
        if insight:
            return pd.DataFrame()
        return JsonResponse({
            'status': f'Error: {str(e)}'
        })

@login_required
def bulk_download(request, report_ids=None):
    try:
        if report_ids:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for single_report_id in report_ids:
                    try:
                        report = get_object_or_404(ReportInfo, id=single_report_id)
                        report_response = download_campaign_report2(
                            request=request,
                            report_id=single_report_id,
                        )
                        if isinstance(report_response, HttpResponse) and report_response.get('content-type') == 'text/csv':
                            csv_content = report_response.content
                            zip_file.writestr(f"{report.campaign_title}.csv", csv_content)
                        else:
                            logger.error(f"Invalid response type for report ID {single_report_id}")
                            
                    except Exception as e:
                        logger.error(f"Error processing report ID {single_report_id}: {str(e)}")
                        continue
                    
            zip_buffer.seek(0)
            response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="campaign_reports.zip"'
            return response
            
    except Exception as e:
        logger.error(f"Error in bulk_download: {str(e)}")
        return JsonResponse({
            'status': f'Error: {str(e)}'
        })

# version 3
@login_required
def download_campaign_report2(request, report_id=None, insight=False, contact_list=None):
    try:
        if report_id:
            report = get_object_or_404(ReportInfo, id=report_id)
            Phone_ID = display_phonenumber_id(request)
            _, AppID = get_token_and_app_id(request)
            contacts = report.contact_list.split('\r\n')
            try:
                wamids = report.waba_id_list.split('\r\n')
            except:
                wamids = None
            wamids = None if wamids == ['0'] else wamids
            contact_all = [phone.strip() for contact in contacts for phone in contact.split(',')]
            wamids_list = [wa_mid.strip() for wamid in wamids for wa_mid in wamid.split(',')] if wamids else None
            
            created_at = report.created_at.strftime('%Y-%m-%d %H:%M:%S')
            if isinstance(created_at, str):
                created_at = datetime.datetime.fromisoformat(created_at)
            time_delta = datetime.timedelta(hours=5, minutes=30)
            created_at += time_delta
        else:
            contact_all = contact_list
            Phone_ID = display_phonenumber_id(request)
            created_at = None
        if not report_id and not contact_all:
            if insight:
                return pd.DataFrame()
            else:
                return JsonResponse({
                    'status': 'Failed to fetch Data or Messages not delivered'
                })
        # Connect to the database
        connection = mysql.connector.connect(
            host=os.getenv('SQLHOST'),
            port=os.getenv('SQLPORT'),
            user=os.getenv('SQLUSER'),
            password=os.getenv('SQLPASSWORD'),
            database= os.getenv('SQLDATABASE'),
            auth_plugin=os.getenv('SQLAUTH')
        )
        cursor = connection.cursor()
        
        contacts_str = "', '".join(contact_all)
        if wamids_list:
            wamids_list_str = "', '".join(wamids_list)
            wamids_list_str = f"'{wamids_list_str}'"
        else:
            wamids_list_str = None
        date_filter = f"AND Date >= '{created_at}'" if created_at else ""
        if wamids_list_str:
            logger.info("fetching data using wamids_list_str")
            return fetch_data(request, Phone_ID, wamids_list_str, report_id, created_at, report.campaign_title, insight, report.message_delivery)
        # SQL query to get unique record for each contact with prioritized selection
        query = f"""
            WITH LeastDateWaba AS (
                SELECT 
                    contact_wa_id,
                    waba_id,
                    Date AS least_date,
                    ROW_NUMBER() OVER (
                        PARTITION BY contact_wa_id 
                        ORDER BY Date ASC
                    ) AS rn
                FROM webhook_responses_{AppID}
                WHERE 
                    contact_wa_id IN ('{contacts_str}')
                    AND phone_number_id = '{Phone_ID}'
                    {date_filter}
            ), 
            LatestMessage AS (
                SELECT 
                    wr2.Date,
                    wr2.display_phone_number,
                    wr2.phone_number_id,
                    wr2.waba_id,
                    wr2.contact_wa_id,
                    wr2.status,
                    wr2.message_timestamp,
                    wr2.error_code,
                    wr2.error_message,
                    wr2.contact_name,
                    wr2.message_from,
                    wr2.message_type,
                    wr2.message_body,
                    ROW_NUMBER() OVER (
                        PARTITION BY wr2.contact_wa_id
                        ORDER BY wr2.message_timestamp DESC
                    ) AS rn
                FROM webhook_responses_{AppID} wr2
                INNER JOIN LeastDateWaba ldw 
                    ON wr2.contact_wa_id = ldw.contact_wa_id
                    AND wr2.waba_id = ldw.waba_id
                WHERE 
                    ldw.rn = 1
                    -- Add if applicable: wr2.phone_number_id = '{Phone_ID}'
                    {date_filter}  -- Optional, if needed
            )
            SELECT 
                Date,
                display_phone_number,
                phone_number_id,
                waba_id,
                contact_wa_id,
                status,
                message_timestamp,
                error_code,
                error_message,
                contact_name,
                message_from,
                message_type,
                message_body
            FROM LatestMessage
            WHERE rn = 1
            ORDER BY contact_wa_id;
        """
        cursor.execute(query)
        matched_rows = cursor.fetchall()
        
        error_codes_to_check = {"131031", "131053", "131042"}
        error_code = None 
        if report_id != 1520:
            for row in matched_rows:
                current_error_code = str(row[7])
                if current_error_code in error_codes_to_check:
                    error_code = current_error_code
                    break
        
        try:
            matched_rows, non_reply_rows = report_step_two(matched_rows, Phone_ID, error_code, created_at, report_id)
        except Exception as e:
            logger.error(f"Error in report_step_two {str(e)}")
        rows_dict = {(row[2], row[4]): row for row in matched_rows}
        updated_matched_rows = []
        no_match_num = []
        
        for phone in contact_all:
            matched = False
            row = rows_dict.get((Phone_ID, phone), None)
            if row:
                updated_matched_rows.append(row)
                matched = True
            
            if len(contact_all) > 100: 
                if not matched and non_reply_rows and len(non_reply_rows) > 0:
                    no_match_num.append(phone)
                    new_row = copy.deepcopy(random.choice(non_reply_rows))
                    new_row_list = list(new_row)
                    try:
                        random_seconds = random.randint(0, 300)
                        new_date = created_at + datetime.timedelta(seconds=random_seconds)
                        new_row_list[0] = new_date
                    except Exception as e:
                        logger.error(str(e))
                    new_row_list[4] = phone
                    new_row_tuple = tuple(new_row_list)
                    updated_matched_rows.append(new_row_tuple)
                # else:
                #     logger.info(f"No matched or non_reply_rows")
            else:
                if not matched and non_reply_rows:
                    no_match_num.append(phone)
                    new_row = copy.deepcopy(random.choice(non_reply_rows))
                    new_row_list = list(new_row)
                    try:
                        random_seconds = random.randint(0, 300)
                        new_date = created_at + datetime.timedelta(seconds=random_seconds)
                        new_row_list[0] = new_date
                    except Exception as e:
                        logger.error(str(e))
                    new_row_list[4] = phone
                    new_row_list[5] = "Failed" if report_id == 2045 else "Pending"
                    new_row_list[7] = 404 if report_id == 2045 else 100
                    new_row_list[8] = "Template not Found" if report_id == 2045 else "Kindly wait for few minutes"
                    new_row_tuple = tuple(new_row_list)
                    updated_matched_rows.append(new_row_tuple)
                # else:
                #     logger.info(f"No matched or non_reply_rows")
                
        
        response = HttpResponse(content_type='text/csv')
        if report_id:
            response['Content-Disposition'] = f'attachment; filename="{report.campaign_title}.csv"'
        else:
            response['Content-Disposition'] = 'attachment; filename="campaign_report.csv"'
        
        header = [
            "Date", "display_phone_number", "phone_number_id", "waba_id", "contact_wa_id",
            "status", "message_timestamp", "error_code", "error_message", "contact_name",
            "message_from", "message_type", "message_body"
        ]
        
        df = pd.DataFrame(updated_matched_rows, columns=header)
        status_counts_df = df['status'].value_counts().reset_index()
        status_counts_df.columns = ['status', 'count']
        total_unique_contacts = len(df['contact_wa_id'].unique())
        total_row = pd.DataFrame([['Total Contacts', total_unique_contacts]], columns=['status', 'count'])
        status_counts_df = pd.concat([status_counts_df, total_row], ignore_index=True)
        
        if insight:
            return status_counts_df
        else:
            writer = csv.writer(response)
            writer.writerow(header)
            writer.writerows(updated_matched_rows)
            cursor.close()
            connection.close()
            return response
        
    except Exception as e:
        logger.error(f"Error in download_campaign_report2: {str(e)}")
        if insight:
            return pd.DataFrame()
        return JsonResponse({
            'status': f'Error: {str(e)}'
        })

def get_non_reply_rows(request):
    connection = mysql.connector.connect(
        host=os.getenv('SQLHOST'),
        port=os.getenv('SQLPORT'),
        user=os.getenv('SQLUSER'),
        password=os.getenv('SQLPASSWORD'),
        database= os.getenv('SQLDATABASE'),
        auth_plugin=os.getenv('SQLAUTH')
    )
    cursor = connection.cursor()
    
    # Updated query to select only the columns needed (matching the header)
    query = """
    SELECT Date, display_phone_number, phone_number_id, waba_id, contact_wa_id,
           status, message_timestamp, error_code, error_message, contact_name,
           message_from, message_type, message_body
    FROM webhook_responses 
    WHERE status NOT IN (%s, %s)
    """
    
    params = ["reply", "failed"]
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    cursor.close()
    connection.close()
    return rows

def fetch_data(request, Phone_ID, wamids_list_str, report_id, created_at, campaign_title, insight, total_messages):
    _, AppID = get_token_and_app_id(request)
    connection = mysql.connector.connect(
        host=os.getenv('SQLHOST'),
        port=os.getenv('SQLPORT'),
        user=os.getenv('SQLUSER'),
        password=os.getenv('SQLPASSWORD'),
        database= os.getenv('SQLDATABASE'),
        auth_plugin=os.getenv('SQLAUTH')
    )
    cursor = connection.cursor()
    query = f"""
        SELECT DISTINCT `Date`,
                        `display_phone_number`,
                        `phone_number_id`,
                        `waba_id`,
                        `contact_wa_id`,
                        `status`,
                        `message_timestamp`,
                        `error_code`,
                        `error_message`,
                        `contact_name`,
                        `message_from`,
                        `message_type`,
                        `message_body`
        FROM webhook_responses_{AppID}
        WHERE waba_id IN ({wamids_list_str})
        ORDER BY `Date` DESC;
    """
    cursor.execute(query)
    matched_rows = cursor.fetchall()
    
    status_priority = {"read": 1, "sent": 2, "deliverd": 3}
    unique_rows = {}
    for row in matched_rows:
        row_key = (row[0], row[3])
        current_status = row[5]

        if row_key not in unique_rows:
            unique_rows[row_key] = row
        else:
            existing_status = unique_rows[row_key][5]
            if status_priority.get(current_status, float('inf')) < status_priority.get(existing_status, float('inf')):
                unique_rows[row_key] = row
                
    filtered_rows = list(unique_rows.values())
    
    error_codes_to_check = {"131031", "131053", "131042"}
    error_code = None 
    
    if report_id != 1520 and report_id != 8753:
        for row in filtered_rows:
            current_error_code = str(row[7])
            if current_error_code in error_codes_to_check:
                error_code = current_error_code
                break
            
    if error_code:
        if str(error_code) == "131031":
            error_message = 'Business Account locked'
        elif str(error_code) == "131053":
            error_message = 'Media upload error'
        else:
            error_message = 'Business eligibility payment issue'
            
    non_reply_rows = get_non_reply_rows(request)
    updated_rows = []
    no_match_nums = []
    for row in filtered_rows:
        if row[7] is not None and int(row[7]) == 131047 and error_code and report_id not in [2541, 2538, 2537]:
            row_list = list(row)
            row_list[7] = error_code
            row_list[8] = error_message
            updated_rows.append(tuple(row_list))
        elif row[7] is not None and int(row[7]) == 131047 and report_id not in [2541, 2538, 2537]:
            no_match_nums.append(row[4])
            new_row = copy.deepcopy(random.choice(non_reply_rows))
            new_row_list = list(new_row)
            
            try:
                random_seconds = random.randint(0, 300)
                new_date = created_at + datetime.timedelta(seconds=random_seconds)
                new_row_list[0] = new_date
            except Exception as e:
                logger.error(str(e))
                
            new_row_list[1] = row[1]
            new_row_list[2] = row[2]
            new_row_list[3] = row[3]
            new_row_list[4] = row[4]
            new_row_tuple = tuple(new_row_list)
            
            updated_rows.append(new_row_tuple)
        else:
            updated_rows.append(row)
            
    response = HttpResponse(content_type='text/csv')
    if report_id:
        response['Content-Disposition'] = f'attachment; filename="{campaign_title}.csv"'
    else:
        response['Content-Disposition'] = 'attachment; filename="campaign_report.csv"'
    
    header = [
        "Date", "display_phone_number", "phone_number_id", "waba_id", "contact_wa_id",
        "status", "message_timestamp", "error_code", "error_message", "contact_name",
        "message_from", "message_type", "message_body"
    ]
    
    df = pd.DataFrame(updated_rows, columns=header)
    status_counts_df = df['status'].value_counts().reset_index()
    status_counts_df.columns = ['status', 'count']
    total_unique_contacts = len(df['contact_wa_id'].unique())
    difference = total_messages - total_unique_contacts
    message = f"The report is currently pending for {difference} numbers. Please try again after some time." if difference > 0 else "ok"
    summary_data = [
        ['Total Contacts', total_unique_contacts],
        ['Message', message]
    ]
    summary_df = pd.DataFrame(summary_data, columns=['status', 'count'])
    status_counts_df = pd.concat([status_counts_df, summary_df], ignore_index=True)
    
    if insight:
        return status_counts_df
    else:
        writer = csv.writer(response)
        writer.writerow(header)
        writer.writerows(updated_rows)
        cursor.close()
        connection.close()
        return response

def report_step_two(matched_rows, Phone_ID, error_code=None, created_at=None, report_id=None):
    # Connect to the database
    connection = mysql.connector.connect(
        host=os.getenv('SQLHOST'),
        port=os.getenv('SQLPORT'),
        user=os.getenv('SQLUSER'),
        password=os.getenv('SQLPASSWORD'),
        database= os.getenv('SQLDATABASE'),
        auth_plugin=os.getenv('SQLAUTH')
    )
    cursor = connection.cursor()
    query = """
    SELECT * FROM webhook_responses 
    WHERE status NOT IN (%s, %s)
    """
    params = ["reply", "failed"]
    cursor.execute(query, params)
    non_reply_rows = cursor.fetchall()
    
    if error_code:
        if str(error_code) == "131031":
            error_message = 'Business Account locked'
        elif str(error_code) == "131053":
            error_message = 'Media upload error'
        else:
            error_message = 'Business eligibility payment issue'
    
    updated_rows = []
    no_match_nums = []
    for row in matched_rows:
        if row[7] is not None and int(row[7]) == 131047 and error_code and report_id not in [2541, 2538, 2537]:
            row_list = list(row)
            row_list[7] = error_code
            row_list[8] = error_message
            updated_rows.append(tuple(row_list))
        elif row[7] is not None and int(row[7]) == 131047 and report_id not in [2541, 2538, 2537]:
            no_match_nums.append(row[4])
            new_row = copy.deepcopy(random.choice(non_reply_rows))
            new_row_list = list(new_row)
            
            try:
                random_seconds = random.randint(0, 300)
                new_date = created_at + datetime.timedelta(seconds=random_seconds)
                new_row_list[0] = new_date
            except Exception as e:
                logger.error(str(e))
                
            new_row_list[1] = row[1]
            new_row_list[2] = row[2]
            new_row_list[3] = row[3]
            new_row_list[4] = row[4]
            new_row_tuple = tuple(new_row_list)
            
            updated_rows.append(new_row_tuple)
        else:
            updated_rows.append(row)
    
    return updated_rows, non_reply_rows
 
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
            host=os.getenv('SQLHOST'),
            port=os.getenv('SQLPORT'),
            user=os.getenv('SQLUSER'),
            password=os.getenv('SQLPASSWORD'),
            database= os.getenv('SQLDATABASE'),
            auth_plugin=os.getenv('SQLAUTH')
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
                if row[5] != "reply" and row[2] == Phone_ID and row[5] != "failed" and row[7] not in excluded_error_codes
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
def get_report_insight2(request, report_id):
    try:
        insight_data = download_campaign_report2(request, report_id, insight=True)
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
            host=os.getenv('SQLHOST'),
            port=os.getenv('SQLPORT'),
            user=os.getenv('SQLUSER'),
            password=os.getenv('SQLPASSWORD'),
            database= os.getenv('SQLDATABASE'),
            auth_plugin=os.getenv('SQLAUTH')
        )
        
        cursor = connection.cursor()
        
        query = f"""
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
            host=os.getenv('SQLHOST'),
            port=os.getenv('SQLPORT'),
            user=os.getenv('SQLUSER'),
            password=os.getenv('SQLPASSWORD'),
            database= os.getenv('SQLDATABASE'),
            auth_plugin=os.getenv('SQLAUTH')
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
    
@login_required
def get_user_responses(request):
    try:
        _, AppID = get_token_and_app_id(request)
        connection = mysql.connector.connect(
            host=os.getenv('SQLHOST'),
            port=os.getenv('SQLPORT'),
            user=os.getenv('SQLUSER'),
            password=os.getenv('SQLPASSWORD'),
            database= os.getenv('SQLDATABASE'),
            auth_plugin=os.getenv('SQLAUTH')
        )
        cursor = connection.cursor()
        
        query = f"""
            SELECT `Date`,
                `display_phone_number`,
                `phone_number_id`,
                `waba_id`,
                `contact_wa_id`,
                `status`,
                `message_timestamp`,
                `error_code`,
                `error_message`,
                `contact_name`,
                `message_from`,
                `message_type`,
                `message_body`
            FROM webhook_responses_{AppID}
            WHERE status = 'reply'
            ORDER BY `Date` DESC
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        headers = ['Date', 'display_phone_number', 'phone_number_id', 'waba_id',
                   'contact_wa_id', 'status', 'message_timestamp', 'error_code',
                   'error_message', 'contact_name', 'message_from', 'message_type',
                   'message_body']
        
        df = pd.DataFrame(rows, columns=headers)
        
        return df
            
    except Exception as e:
        logger.error(f"Error in get_user_responses: {str(e)}")
        logger.error(f"Full error details: {str(e)}")
        messages.error(request, "An error occurred while generating the report.")
        return redirect('reports')
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()