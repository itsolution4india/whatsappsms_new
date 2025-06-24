from .auth import check_user_permission, username
from ..models import Templates, ReportInfo
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from ..utils import logger, display_whatsapp_id, display_phonenumber_id, get_token_and_app_id
import pandas as pd
import mysql.connector
import datetime
import csv, copy, random
from django.http import HttpResponse, JsonResponse
from ..functions.template_msg import fetch_templates
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


from dotenv import load_dotenv
import os
from django.utils import timezone

load_dotenv()

@login_required
def Reports_new(request):
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

# version 4
@login_required
def download_campaign_report_new(request, report_id=None, insight=False, contact_list=None):
    try:
        if report_id:
            report = get_object_or_404(ReportInfo, id=report_id)
            contacts = report.contact_list.split('\r\n')
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
            updated_at = report.updated_at.strftime('%Y-%m-%d %H:%M:%S')
            if isinstance(created_at, str):
                created_at = datetime.datetime.fromisoformat(created_at)
            if isinstance(updated_at, str):
                updated_at = datetime.datetime.fromisoformat(updated_at)
            time_delta = datetime.timedelta(hours=5, minutes=30)
            created_at += time_delta
            updated_at += time_delta
        else:
            contact_all = contact_list
            created_at = None
            time_delta = None
        if not report_id and not contact_all:
            if insight:
                return pd.DataFrame()
            else:
                return JsonResponse({
                    'status': 'Failed to fetch Data or Messages not delivered'
                })
                
        contacts_str = "', '".join(contact_all)
        if wamids_list:
            wamids_list_str = "', '".join(wamids_list)
            wamids_list_str = f"'{wamids_list_str}'"
        else:
            wamids_list_str = None
        date_filter = f"AND Date >= '{created_at}'" if created_at else ""
        
        now = timezone.now()
        if timezone.is_naive(created_at):
            created_at = timezone.make_aware(created_at)
        if timezone.is_naive(updated_at):
            updated_at = timezone.make_aware(updated_at)

        time_since_created = now - created_at
        time_since_updated = now - updated_at

        counts = [
            report.deliver_count,
            report.sent_count,
            report.read_count,
            report.failed_count,
            report.reply_count
        ]

        # CASE 1: created_at is older than 24 hours
        if time_since_created.total_seconds() > 86400 and insight:
            if any(count > 0 for count in counts):
                status_counts_df = pd.DataFrame([
                    ['deliverd', report.deliver_count],
                    ['sent', report.sent_count],
                    ['read', report.read_count],
                    ['failed', report.failed_count],
                    ['reply', report.reply_count],
                    ['Total Contacts', report.total_count]
                ], columns=['status', 'count'])
                return status_counts_df
            elif wamids_list_str:
                return fetch_data_using_wamids(request, wamids_list_str, report_id, created_at, report.campaign_title, insight)
            else:
                try:
                    featch_data_using_numbers(AppID, Phone_ID, contacts_str, date_filter, report_id, created_at, contact_all, report, insight)
                except Exception as e:
                    logger.error(f"Error in featch_data_using_numbers: {e}")

        # CASE 2: created_at is within 24 hours
        else:
            if time_since_updated.total_seconds() < 600 and any(count > 0 for count in counts) and insight:
                status_counts_df = pd.DataFrame([
                    ['deliverd', report.deliver_count],
                    ['sent', report.sent_count],
                    ['read', report.read_count],
                    ['failed', report.failed_count],
                    ['reply', report.reply_count],
                    ['Total Contacts', report.total_count]
                ], columns=['status', 'count'])
                return status_counts_df
            elif wamids_list_str:
                return fetch_data_using_wamids(request, wamids_list_str, report_id, created_at, report.campaign_title, insight)
            else:
                try:
                    featch_data_using_numbers(AppID, Phone_ID, contacts_str, date_filter, report_id, created_at, contact_all, report, insight)
                except Exception as e:
                    logger.error(f"Error in featch_data_using_numbers: {e}")
                    
    except Exception as e:
        logger.error(f"Error in download_campaign_report_new: {str(e)}")
        if insight:
            return pd.DataFrame()
        return JsonResponse({
            'status': f'Error: {str(e)}'
        })

def get_non_reply_rows():
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

def update_report_insights(report_id, status_df):
    try:
        report = ReportInfo.objects.get(id=report_id)
        deliver_count = sent_count = read_count = failed_count = reply_count = 0

        for _, row in status_df.iterrows():
            status = row['status']
            count = row['count']
            if status == 'delivered':
                deliver_count = count
            elif status == 'sent':
                sent_count = count
            elif status == 'read':
                read_count = count
            elif status == 'seen':
                read_count = read_count + count
            elif status == 'failed':
                failed_count = count
            elif status == 'reply':
                reply_count = count

        report.deliver_count = deliver_count
        report.sent_count = sent_count
        report.read_count = read_count
        report.failed_count = failed_count
        report.reply_count = reply_count
        report.total_count = deliver_count + sent_count + read_count + failed_count + reply_count
        report.updated_at = timezone.now()
        report.save()
    except ReportInfo.DoesNotExist:
        logger.error(f"ReportInfo with id {report_id} does not exist")
    except Exception as e:
        logger.error(f"Error updating report insights: {str(e)}")

def fetch_data_using_wamids(request, wamids_list_str, report_id, created_at, campaign_title, insight):
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
            
    non_reply_rows = get_non_reply_rows()
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
    total_row = pd.DataFrame([['Total Contacts', total_unique_contacts]], columns=['status', 'count'])
    status_counts_df = pd.concat([status_counts_df, total_row], ignore_index=True)
    
    update_report_insights(report_id, status_counts_df)
    if insight:
        return status_counts_df
    else:
        writer = csv.writer(response)
        writer.writerow(header)
        writer.writerows(updated_rows)
        cursor.close()
        connection.close()
        return response
 
def featch_data_using_numbers(AppID, Phone_ID, contacts_str, date_filter, report_id, created_at, contact_all, report, insight):
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
    
    update_report_insights(report_id, status_counts_df)
    if insight:
        return status_counts_df
    else:
        writer = csv.writer(response)
        writer.writerow(header)
        writer.writerows(updated_matched_rows)
        cursor.close()
        connection.close()
        return response
        
def report_step_two(matched_rows, Phone_ID, error_code=None, created_at=None, report_id=None):
    non_reply_rows = get_non_reply_rows()
    
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
def get_report_insight_new(request, report_id):
    try:
        insight_data = download_campaign_report_new(request, report_id, insight=True)
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
        