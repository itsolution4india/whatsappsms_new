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
    conn = None
    cursor = None
    
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
        successful_inserts = 0
        failed_inserts = 0
        
        for _, row in df.iterrows():
            # Start a new transaction for each row
            try:
                # Convert message_date from string to date object
                message_date = datetime.strptime(str(row['message_date']), '%m/%d/%Y').date()
                
                # Clean contact_list
                contact_list = clean_contact_list(row['contact_list'])
                
                # Prepare created_at timestamp with better handling
                created_at = datetime.now()
                if 'created_at' in row and pd.notna(row['created_at']):
                    try:
                        # Handle time format with improved parsing
                        time_str = str(row['created_at'])
                        if ':' in time_str:
                            # Add today's date to make it a complete datetime
                            today = datetime.now().date()
                            time_parts = time_str.split(':')
                            if len(time_parts) >= 2:
                                hour = int(time_parts[0])
                                minute = int(float(time_parts[1]))
                                created_at = datetime.combine(today, datetime.min.time().replace(
                                    hour=hour % 24,  # Handle cases where hour > 24
                                    minute=minute % 60  # Handle cases where minute > 60
                                ))
                    except (ValueError, IndexError) as e:
                        print(f"Warning: Could not parse created_at time '{time_str}', using current time. Error: {e}")
                
                # Insert query
                insert_query = """
                    INSERT INTO smsapp_reportinfo 
                    (campaign_title, message_date, message_delivery, email, 
                     template_name, contact_list, end_request_id, start_request_id, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                # Prepare values with additional data validation
                values = (
                    str(row['campaign_title']).strip(),
                    message_date,
                    int(float(row['message_delivery'])) if pd.notna(row['message_delivery']) else 0,
                    str(row['email']).strip().lower(),
                    str(row['template_name']).strip(),
                    contact_list,
                    int(float(row['end_request_id'])) if pd.notna(row['end_request_id']) else 0,
                    int(float(row['start_request_id'])) if pd.notna(row['start_request_id']) else 0,
                    created_at
                )
                
                # Execute insert within its own transaction
                cursor.execute("BEGIN")
                cursor.execute(insert_query, values)
                cursor.execute("COMMIT")
                
                successful_inserts += 1
                print(f"Inserted record for campaign: {row['campaign_title']}")
                
            except Exception as e:
                cursor.execute("ROLLBACK")  # Rollback the transaction for this row
                failed_inserts += 1
                print(f"Error processing row {_}:")
                print(f"Data: {row.to_dict()}")
                print(f"Error details: {str(e)}")
                continue
        
        print(f"\nImport Summary:")
        print(f"Successfully inserted: {successful_inserts} records")
        print(f"Failed to insert: {failed_inserts} records")
        print("Data import completed!")
        
    except Exception as e:
        print(f"Critical error during import: {str(e)}")
        if conn:
            conn.rollback()
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    # Database configuration
    db_config = {
        'NAME': 'admin',
        'USER': 'postgres',
        'PASSWORD': 'Solution@97',
        'HOST': '217.145.69.172',
        'PORT': '5432'
    }
    
    # CSV file path
    csv_file = 'smsapp_reportinfo2.csv'
    
    # Import data
    import_report_info(csv_file, db_config)