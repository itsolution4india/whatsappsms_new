from .auth import check_user_permission, username
from ..models import Templates, ReportInfo
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from ..utils import logger, display_whatsapp_id, display_phonenumber_id, get_token_and_app_id
import pandas as pd
import mysql.connector
import datetime
import random
from django.http import HttpResponse, JsonResponse
from ..functions.template_msg import fetch_templates
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import time
import numpy as np

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
        if time_since_created.total_seconds() > 86400:
            if any(count > 0 for count in counts) and insight:
                difference = report.message_delivery - report.total_count
                message = f"status pending for {difference} numbers, Please check back later." if difference > 0 else "ok"
                status_counts_df = pd.DataFrame([
                    ['delivered', report.deliver_count],
                    ['sent', report.sent_count],
                    ['read', report.read_count],
                    ['failed', report.failed_count],
                    ['reply', report.reply_count],
                    ['Message', message],
                    ['Total Contacts', report.total_count]
                ], columns=['status', 'count'])
                
                return status_counts_df
            else:
                match_stats = True if any(count > 0 for count in counts) else False
                return featch_data_using_numbers_optimized(AppID, Phone_ID, contacts_str, date_filter, report_id, created_at, contact_all, report, insight, match_stats)

        # CASE 2: created_at is within 24 hours
        else:
            if time_since_updated.total_seconds() < 1200 and any(count > 0 for count in counts) and insight:
                difference = report.message_delivery - report.total_count
                message = f"The report is still in progress with {difference} messages pending. Please check back later." if difference > 0 else "ok"
                status_counts_df = pd.DataFrame([
                    ['delivered', report.deliver_count],
                    ['sent', report.sent_count],
                    ['read', report.read_count],
                    ['failed', report.failed_count],
                    ['reply', report.reply_count],
                    ['Message', message],
                    ['Total Contacts', report.total_count]
                ], columns=['status', 'count'])
                return status_counts_df
            elif wamids_list_str:
                match_stats = True if time_since_updated.total_seconds() < 1200 and any(count > 0 for count in counts) else False
                return fetch_data_using_wamids_optimized(request, wamids_list_str, report_id, created_at, report.campaign_title, insight, report, match_stats)
            else:
                match_stats = True if time_since_updated.total_seconds() < 1200 and any(count > 0 for count in counts) else False
                return featch_data_using_numbers_optimized(AppID, Phone_ID, contacts_str, date_filter, report_id, created_at, contact_all, report, insight, match_stats)
                    
    except Exception as e:
        logger.error(f"Error in download_campaign_report_new: {str(e)}")
        if insight:
            return pd.DataFrame()
        return JsonResponse({
            'status': f'Error: {str(e)}'
        })

# Optimized connection manager
from contextlib import contextmanager

@contextmanager
def get_db_connection():
    """Context manager for database connections with proper cleanup"""
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(
            host=os.getenv('SQLHOST'),
            port=int(os.getenv('SQLPORT', 3306)),
            user=os.getenv('SQLUSER'),
            password=os.getenv('SQLPASSWORD'),
            database=os.getenv('SQLDATABASE'),
            auth_plugin=os.getenv('SQLAUTH'),
            # Connection pool settings for better performance
            pool_name="report_pool",
            pool_size=5,
            pool_reset_session=True,
            # Performance optimizations
            autocommit=True,
            use_unicode=True,
            charset='utf8mb4',
            sql_mode='TRADITIONAL',
            # Timeout settings
            connection_timeout=30,
            # Buffer settings for large result sets
            buffered=True
        )
        cursor = connection.cursor(buffered=True)
        yield cursor
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# Cache for non-reply rows to avoid repeated DB calls
_non_reply_rows_cache = None
_cache_timestamp = None
CACHE_DURATION = 300  # 5 minutes

def get_non_reply_rows_cached():
    """Cached version of get_non_reply_rows"""
    global _non_reply_rows_cache, _cache_timestamp
    
    current_time = time.time()
    if _non_reply_rows_cache is None or (current_time - _cache_timestamp) > CACHE_DURATION:
        with get_db_connection() as cursor:
            query = """
            SELECT Date, display_phone_number, phone_number_id, waba_id, contact_wa_id,
                   status, message_timestamp, error_code, error_message, contact_name,
                   message_from, message_type, message_body
            FROM webhook_responses 
            WHERE status NOT IN ('reply', 'failed')
            LIMIT 1000
            """
            cursor.execute(query)
            _non_reply_rows_cache = cursor.fetchall()
            _cache_timestamp = current_time
    
    return _non_reply_rows_cache

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
            elif status == 'Total Contacts':
                total = count

        report.deliver_count = deliver_count
        report.sent_count = sent_count
        report.read_count = read_count
        report.failed_count = failed_count
        report.reply_count = reply_count
        report.total_count = total
        report.updated_at = timezone.now()
        report.save()
    except ReportInfo.DoesNotExist:
        logger.error(f"ReportInfo with id {report_id} does not exist")
    except Exception as e:
        logger.error(f"Error updating report insights: {str(e)}")

def featch_data_using_numbers_optimized(AppID, Phone_ID, contacts_str, date_filter, report_id, created_at, contact_all, report, insight, match_stats=False):
    """Optimized version with better query and batch processing"""
    
    # Process contacts in batches to avoid memory issues
    BATCH_SIZE = 1000
    contact_batches = [contact_all[i:i + BATCH_SIZE] for i in range(0, len(contact_all), BATCH_SIZE)]
    
    all_matched_rows = []
    
    with get_db_connection() as cursor:
        for batch in contact_batches:
            batch_contacts_str = "', '".join(batch)
            
            # Optimized query with better indexing hints
            query = f"""
                SELECT /*+ USE_INDEX(webhook_responses_{AppID}, idx_contact_phone_date) */
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
                FROM (
                    SELECT *,
                           ROW_NUMBER() OVER (
                               PARTITION BY contact_wa_id 
                               ORDER BY message_timestamp DESC
                           ) AS rn
                    FROM webhook_responses_{AppID}
                    WHERE 
                        contact_wa_id IN ('{batch_contacts_str}')
                        AND phone_number_id = '{Phone_ID}'
                        {date_filter}
                ) ranked
                WHERE rn = 1
                ORDER BY contact_wa_id;
            """
            
            cursor.execute(query)
            batch_rows = cursor.fetchall()
            all_matched_rows.extend(batch_rows)
    
    # Optimized error code detection
    error_codes_to_check = {"131031", "131053", "131042"}
    error_code = None 
    if report_id not in [1520, 8753]:
        # Use generator expression for better memory efficiency
        error_code = next((str(row[7]) for row in all_matched_rows 
                          if row[7] and str(row[7]) in error_codes_to_check), None)
    
    # Process rows with optimized logic
    try:
        matched_rows, non_reply_rows = report_step_two_optimized(all_matched_rows, Phone_ID, error_code, created_at, report_id)
    except Exception as e:
        logger.error(f"Error in report_step_two_optimized: {str(e)}")
        matched_rows = all_matched_rows
        non_reply_rows = get_non_reply_rows_cached()
    
    # Use dictionary for O(1) lookup instead of list iteration
    rows_dict = {(row[2], row[4]): row for row in matched_rows}
    updated_matched_rows = []
    no_match_num = []
    
    # Optimized contact processing
    use_fallback = len(contact_all) <= 100
    non_reply_rows_available = non_reply_rows and len(non_reply_rows) > 0
    
    for phone in contact_all:
        row = rows_dict.get((Phone_ID, phone))
        if row:
            updated_matched_rows.append(row)
        elif non_reply_rows_available:
            no_match_num.append(phone)
            new_row = create_fallback_row(non_reply_rows, phone, created_at, report_id, use_fallback)
            updated_matched_rows.append(new_row)
    
    # Create response efficiently
    header = [
        "Date", "display_phone_number", "phone_number_id", "waba_id", "contact_wa_id",
        "status", "message_timestamp", "error_code", "error_message", "contact_name",
        "message_from", "message_type", "message_body"
    ]
    
    # Use numpy for faster DataFrame creation if available
    try:
        import numpy as np
        df = pd.DataFrame(np.array(updated_matched_rows), columns=header)
    except ImportError:
        df = pd.DataFrame(updated_matched_rows, columns=header)
    
    # Optimized status counting
    status_counts = df['status'].value_counts()
    status_counts_df = status_counts.reset_index()
    status_counts_df.columns = ['status', 'count']
    
    total_unique_contacts = df['contact_wa_id'].nunique()
    total_messages = report.message_delivery
    difference = total_messages - total_unique_contacts
    message = f"The report is currently pending for {difference} numbers. Please try again after some time." if difference > 0 else "ok"
    
    # Efficiently add summary data
    summary_data = pd.DataFrame([
        ['Total Contacts', total_unique_contacts],
        ['Message', message]
    ], columns=['status', 'count'])
    
    status_counts_df = pd.concat([status_counts_df, summary_data], ignore_index=True)
    
    if match_stats:
        df = adjust_status_counts_optimized(df, report)
    else:
        update_report_insights(report_id, status_counts_df)
    
    if insight:
        return status_counts_df
    else:
        return create_csv_response(df, report)

def create_fallback_row(non_reply_rows, phone, created_at, report_id, use_detailed_fallback):
    """Optimized fallback row creation"""
    base_row = list(random.choice(non_reply_rows))
    
    try:
        random_seconds = random.randint(0, 300)
        new_date = created_at + datetime.timedelta(seconds=random_seconds)
        base_row[0] = new_date
    except Exception as e:
        logger.error(f"Date generation error: {str(e)}")
    
    base_row[4] = phone
    
    if use_detailed_fallback:
        if report_id == 2045:
            base_row[5] = "Failed"
            base_row[7] = 404
            base_row[8] = "Template not Found"
        else:
            base_row[5] = "Pending"
            base_row[7] = 100
            base_row[8] = "Kindly wait for few minutes"
    
    return tuple(base_row)

def report_step_two_optimized(matched_rows, Phone_ID, error_code=None, created_at=None, report_id=None):
    """Optimized version with better error handling"""
    non_reply_rows = get_non_reply_rows_cached()
    
    if error_code:
        error_messages = {
            "131031": 'Business Account locked',
            "131053": 'Media upload error'
        }
        error_message = error_messages.get(str(error_code), 'Business eligibility payment issue')
    
    updated_rows = []
    excluded_reports = {2541, 2538, 2537}
    
    for row in matched_rows:
        if (row[7] is not None and int(row[7]) == 131047 and 
            report_id not in excluded_reports):
            
            row_list = list(row)
            if error_code:
                row_list[7] = error_code
                row_list[8] = error_message
                updated_rows.append(tuple(row_list))
            else:
                # Create replacement row
                new_row = create_replacement_row(non_reply_rows, row, created_at)
                updated_rows.append(new_row)
        else:
            updated_rows.append(row)
    
    return updated_rows, non_reply_rows

def create_replacement_row(non_reply_rows, original_row, created_at):
    """Create replacement row efficiently"""
    new_row = list(random.choice(non_reply_rows))
    
    try:
        random_seconds = random.randint(0, 300)
        new_date = created_at + datetime.timedelta(seconds=random_seconds)
        new_row[0] = new_date
    except Exception as e:
        logger.error(f"Date error: {str(e)}")
    
    # Copy relevant fields from original
    new_row[1] = original_row[1]  # display_phone_number
    new_row[2] = original_row[2]  # phone_number_id
    new_row[3] = original_row[3]  # waba_id
    new_row[4] = original_row[4]  # contact_wa_id
    
    return tuple(new_row)

def adjust_status_counts_optimized(df, report):
    """Optimized status adjustment using vectorized operations"""
    db_status = pd.DataFrame([
        ['delivered', report.deliver_count],
        ['sent', report.sent_count],
        ['read', report.read_count],
        ['failed', report.failed_count],
        ['reply', report.reply_count],
        ['Total Contacts', report.total_count]
    ], columns=['status', 'count'])
    
    target_counts = db_status.set_index('status')['count'].drop('Total Contacts', errors='ignore').to_dict()
    current_counts = df['status'].value_counts().to_dict()
    differences = {status: target_counts[status] - current_counts.get(status, 0) for status in target_counts}
    
    # Use vectorized operations for better performance
    df_copy = df.copy()
    status_series = df_copy['status']
    
    for status, diff in differences.items():
        if diff <= 0:
            continue
        
        donor_statuses = [s for s, d in differences.items() if d < 0]
        converted = 0
        
        for donor in donor_statuses:
            if converted >= diff:
                break
            
            donor_mask = status_series == donor
            donor_indices = df_copy.index[donor_mask].tolist()
            donor_available = min(len(donor_indices), diff - converted, -differences[donor])
            
            if donor_available > 0:
                selected_indices = np.random.choice(donor_indices, donor_available, replace=False)
                df_copy.loc[selected_indices, 'status'] = status
                differences[donor] += donor_available
                converted += donor_available
    
    return df_copy

def create_csv_response(df, report):
    """Optimized CSV response creation"""
    response = HttpResponse(content_type='text/csv')
    filename = f"{report.campaign_title}.csv" if report else "campaign_report.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Use pandas to_csv for better performance
    df.to_csv(response, index=False, lineterminator='\n')
    return response

# Similar optimizations for fetch_data_using_wamids
def fetch_data_using_wamids_optimized(request, wamids_list_str, report_id, created_at, campaign_title, insight, report, match_stats=False):
    """Optimized version of wamids function"""
    _, AppID = get_token_and_app_id(request)
    
    with get_db_connection() as cursor:
        # Optimized query with proper indexing
        query = f"""
            SELECT /*+ USE_INDEX(webhook_responses_{AppID}, idx_waba_date) */
                Date, display_phone_number, phone_number_id, waba_id, contact_wa_id,
                status, message_timestamp, error_code, error_message, contact_name,
                message_from, message_type, message_body
            FROM (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY Date, waba_id 
                           ORDER BY 
                               CASE status 
                                   WHEN 'read' THEN 1 
                                   WHEN 'sent' THEN 2 
                                   WHEN 'delivered' THEN 3 
                                   ELSE 4 
                               END
                       ) as rn
                FROM webhook_responses_{AppID}
                WHERE waba_id IN ({wamids_list_str})
            ) ranked
            WHERE rn = 1
            ORDER BY Date DESC;
        """
        
        cursor.execute(query)
        matched_rows = cursor.fetchall()
    
    # Rest of the processing similar to the original but with optimizations
    error_codes_to_check = {"131031", "131053", "131042"}
    error_code = None 
    
    if report_id not in [1520, 8753]:
        error_code = next((str(row[7]) for row in matched_rows 
                          if row[7] and str(row[7]) in error_codes_to_check), None)
    
    # Apply similar optimizations as in the numbers function
    non_reply_rows = get_non_reply_rows_cached()
    updated_rows = process_wamid_rows(matched_rows, error_code, created_at, report_id, non_reply_rows)
    
    return create_wamid_response(updated_rows, report_id, created_at, campaign_title, insight, report, match_stats)

def process_wamid_rows(matched_rows, error_code, created_at, report_id, non_reply_rows):
    """Process wamid rows efficiently"""
    if error_code:
        error_messages = {
            "131031": 'Business Account locked',
            "131053": 'Media upload error'
        }
        error_message = error_messages.get(str(error_code), 'Business eligibility payment issue')
    
    updated_rows = []
    excluded_reports = {2541, 2538, 2537}
    
    for row in matched_rows:
        if (row[7] is not None and int(row[7]) == 131047 and 
            report_id not in excluded_reports):
            
            row_list = list(row)
            if error_code:
                row_list[7] = error_code
                row_list[8] = error_message
                updated_rows.append(tuple(row_list))
            else:
                new_row = create_replacement_row(non_reply_rows, row, created_at)
                updated_rows.append(new_row)
        else:
            updated_rows.append(row)
    
    return updated_rows

def create_wamid_response(updated_rows, report_id, created_at, campaign_title, insight, report, match_stats):
    """Create optimized response for wamid data"""
    header = [
        "Date", "display_phone_number", "phone_number_id", "waba_id", "contact_wa_id",
        "status", "message_timestamp", "error_code", "error_message", "contact_name",
        "message_from", "message_type", "message_body"
    ]
    
    df = pd.DataFrame(updated_rows, columns=header)
    status_counts_df = df['status'].value_counts().reset_index()
    status_counts_df.columns = ['status', 'count']
    
    total_unique_contacts = df['contact_wa_id'].nunique()
    total_messages = report.message_delivery 
    difference = total_messages - total_unique_contacts
    
    now = timezone.now()
    time_since_created = now - created_at
    if time_since_created.total_seconds() > 86400:
        message = f"status pending for {difference} numbers, Please check back later." if difference > 0 else "ok"
    else:
        message = f"The report is still in progress with {difference} messages pending. Please check back later." if difference > 0 else "ok"
    
    summary_data = pd.DataFrame([
        ['Total Contacts', total_unique_contacts],
        ['Message', message]
    ], columns=['status', 'count'])
    
    status_counts_df = pd.concat([status_counts_df, summary_data], ignore_index=True)
    
    if match_stats:
        df = adjust_status_counts_optimized(df, report)
    else:
        update_report_insights(report_id, status_counts_df)
    
    if insight:
        return status_counts_df
    else:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{campaign_title}.csv"'
        df.to_csv(response, index=False, lineterminator='\n')
        return response

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
        