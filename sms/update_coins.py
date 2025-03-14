import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime

# Database configuration
db_config = {
    'NAME': 'admin',
    'USER': 'postgres',
    'PASSWORD': 'Solution@97',
    'HOST': '217.145.69.172',
    'PORT': '5432'
}

# Function to import data from CSV to PostgreSQL
def import_coins_history(csv_file, db_config):
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

        # Insert query with escaped "user"
        insert_query = """
        INSERT INTO coins_history ("user", type, number_of_coins, created_at, reason, transaction_id)
        VALUES %s
        ON CONFLICT (transaction_id) DO NOTHING
        """

        # Prepare data for bulk insert
        data = []
        for _, row in df.iterrows():
            # Handle created_at with better parsing and rounding for decimal times
            created_at = datetime.now()  # Default to current datetime
            try:
                time_str = str(row['created_at'])
                if ':' in time_str:
                    today = datetime.now().date()
                    hour, minute = time_str.split(':')
                    # Handle decimal cases (e.g., '22.1', '57.9') by rounding them to the nearest valid int
                    hour = int(float(hour)) % 24  # Ensure hour is valid (0-23)
                    minute = int(float(minute)) % 60  # Ensure minute is valid (0-59)
                    created_at = datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute))
            except Exception as e:
                print(f"Warning: Could not parse created_at for {row['transaction_id']}, using current time. Error: {e}")
            
            # Add the row to data list for insertion
            data.append((
                row['user'].strip(),
                row['type'].strip(),
                int(row['number_of_coins']),
                created_at,
                row['reason'].strip(),
                row['transaction_id'].strip()
            ))

        # Execute bulk insert
        execute_values(cursor, insert_query, data)
        conn.commit()
        print(f"Successfully inserted {len(data)} records.")

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error during database insert: {str(e)}")
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    # CSV file path
    csv_file = 'smsapp_coinshistory.csv'  # Ensure the CSV is in the same directory as this script
    
    # Import data
    import_coins_history(csv_file, db_config)
