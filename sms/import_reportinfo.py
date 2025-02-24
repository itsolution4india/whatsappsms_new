# import_reportinfo.py
import pandas as pd
import psycopg2
from datetime import datetime
from psycopg2.extras import execute_values
import numpy as np

def clean_contact_list(value):
    """Clean and format contact list values"""
    if isinstance(value, float) and np.isnan(value):
        return ""
    # Convert scientific notation to regular number and then to string
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    return str(value)

def import_report_info(csv_file, db_config):
    """Import ReportInfo data from CSV to PostgreSQL"""
    try:
        # Read CSV file
        df = pd.read_csv(csv_file)
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            dbname=db_config['NAME'],
            user=db_config['USER'],
            password=db_config['PASSWORD'],
            host=db_config['HOST'],
            port=db_config['PORT']
        )
        cursor = conn.cursor()
        
        # Process data
        for _, row in df.iterrows():
            try:
                # Convert message_date from string to date object
                message_date = datetime.strptime(str(row['message_date']), '%m/%d/%Y').date()
                
                # Clean contact_list
                contact_list = clean_contact_list(row['contact_list'])
                
                # Prepare created_at timestamp
                created_at = datetime.now()
                if 'created_at' in row and pd.notna(row['created_at']):
                    try:
                        created_at = datetime.strptime(str(row['created_at']), '%H:%M.%S')
                    except ValueError:
                        pass  # Keep default if parsing fails
                
                # Insert query
                insert_query = """
                    INSERT INTO smsapp_reportinfo 
                    (campaign_title, message_date, message_delivery, email, 
                     template_name, contact_list, end_request_id, start_request_id, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                # Prepare values
                values = (
                    str(row['campaign_title']),
                    message_date,
                    int(float(row['message_delivery'])) if pd.notna(row['message_delivery']) else 0,
                    str(row['email']),
                    str(row['template_name']),
                    contact_list,
                    int(float(row['end_request_id'])) if pd.notna(row['end_request_id']) else 0,
                    int(float(row['start_request_id'])) if pd.notna(row['start_request_id']) else 0,
                    created_at
                )
                
                # Execute insert
                cursor.execute(insert_query, values)
                print(f"Inserted record for campaign: {row['campaign_title']}")
                
            except Exception as e:
                print(f"Error processing row: {row}")
                print(f"Error details: {str(e)}")
                continue
        
        # Commit the transaction
        conn.commit()
        print("Data import completed successfully!")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    # Database configuration
    db_config = {
        'NAME': 'admin',
        'USER': 'itsolutions',
        'PASSWORD': 'Solution@97',
        'HOST': 'localhost',
        'PORT': '5432'
    }
    
    # CSV file path
    csv_file = 'smsapp_reportinfo2.csv'
    
    # Import data
    import_report_info(csv_file, db_config)