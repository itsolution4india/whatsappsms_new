import json
import psycopg2
from datetime import datetime
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def convert_sqlite_value(value, is_boolean=False, is_date=False, is_timestamp=False):
    """Convert SQLite values to PostgreSQL compatible values"""
    if value is None:
        return None
    
    if is_boolean:
        # Convert integer 1/0 or string '1'/'0' to True/False
        if isinstance(value, (int, str)):
            return bool(int(value))
        return bool(value)
    
    if is_date:
        try:
            if isinstance(value, int):
                # If it's an integer, use a default date
                return datetime(2024, 1, 1).date()
            return datetime.strptime(str(value), '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return datetime(2024, 1, 1).date()  # Default date if conversion fails
    
    if is_timestamp:
        try:
            # Check if the value is an integer (Unix timestamp)
            if isinstance(value, int):
                return datetime.fromtimestamp(value)  # Convert Unix timestamp to datetime
            # Otherwise, try to convert it from string format
            return datetime.strptime(str(value), '%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            return datetime(2024, 1, 1)  # Default timestamp if conversion fails
    
    return value

def load_backup_from_json(json_file_path):
    """Load backup data from a JSON file"""
    print(f"Loading backup data from {json_file_path}...")
    try:
        with open(json_file_path, 'r') as f:
            backup_data = json.load(f)
        print(f"Successfully loaded backup data with {len(backup_data)} tables")
        return backup_data
    except Exception as e:
        print(f"Error loading backup data: {str(e)}")
        return None

def check_table_exists(cursor, table_name):
    """Check if a table exists in PostgreSQL"""
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        );
    """, (table_name,))
    return cursor.fetchone()[0]

# Updated table order to respect foreign key constraints
TABLE_ORDER = [
    'django_migrations',
    'django_content_type',
    'auth_permission',
    'auth_group',
    'smsapp_registerapp',      # Must come before customuser
    'smsapp_customuser',       # Must come after registerapp
    'auth_group_permissions',
    'smsapp_customuser_user_permissions',
    'django_admin_log',
    'django_session',
    'smsapp_templates',
    'smsapp_whitelist_blacklist',
    'smsapp_templatelinkage',
    'smsapp_messageresponse',
    'smsapp_coinshistory',
    'smsapp_flows',
    'smsapp_countrypermission',
    'smsapp_botsentmessages',
    'smsapp_train_wit_bot',
    'smsapp_validate_twoauth',
    'smsapp_useraccess',
    'smsapp_notifications',
    'smsapp_reportinfo',
    'smsapp_last_replay_data',
    'smsapp_scheduledmessage'
]

# Updated boolean fields mapping
BOOLEAN_FIELDS = {
    'smsapp_customuser': ['is_superuser', 'is_staff', 'is_active'],
    'smsapp_countrypermission': [
        'can_send_msg_to_india', 'can_send_msg_to_us', 'can_send_msg_to_uk',
        'can_send_msg_to_australia', 'can_send_msg_to_uae', 'can_send_msg_to_nepal'
    ],
    'smsapp_useraccess': [
        'can_access_api_doc', 'can_send_sms', 'can_manage_users',
        'can_manage_templates', 'can_enable_number_validation',
        'can_enable_2fauth', 'can_view_reports'
    ],
    'smsapp_scheduledmessage': ['is_sent', 'admin_schedule'],
    'smsapp_reportinfo': ['status']
}

DATE_FIELDS = {
    'smsapp_reportinfo': ['message_date']
}

def handle_reportinfo_data(value):
    """Handle integer overflow in reportinfo table"""
    try:
        return int(value)
    except (OverflowError, ValueError):
        return 0

def restore_to_postgres(backup_data, db_name, user, password, host='localhost', port='5432'):
    """Restore data to PostgreSQL database"""
    connection = psycopg2.connect(
        dbname=db_name,
        user=user,
        password=password,
        host=host,
        port=port
    )
    connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = connection.cursor()
    
    for table_name in TABLE_ORDER:
        if table_name not in backup_data:
            print(f"Skipping table {table_name} as it's not in the backup data")
            continue
            
        try:
            table_info = backup_data[table_name]
            
            if not check_table_exists(cursor, table_name):
                print(f"Skipping table {table_name} as it doesn't exist in PostgreSQL")
                continue

            if not table_info['data']:
                continue
                
            cursor.execute(f'TRUNCATE TABLE "{table_name}" CASCADE;')
                
            columns = table_info['columns']
            placeholders = ','.join(['%s'] * len(columns))
            column_names = ','.join(f'"{col}"' for col in columns)
            
            insert_query = f'INSERT INTO "{table_name}" ({column_names}) VALUES ({placeholders})'
            
            batch_size = 1000
            for i in range(0, len(table_info['data']), batch_size):
                batch = table_info['data'][i:i + batch_size]
                batch_values = []
                for row in batch:
                    values = []
                    for col in columns:
                        value = row[col]
                        
                        # Handle different field types
                        if table_name in BOOLEAN_FIELDS and col in BOOLEAN_FIELDS[table_name]:
                            value = convert_sqlite_value(value, is_boolean=True)
                        elif table_name in DATE_FIELDS and col in DATE_FIELDS[table_name]:
                            value = convert_sqlite_value(value, is_date=True)
                        elif table_name == 'smsapp_reportinfo' and col == 'created_at':
                            value = convert_sqlite_value(value, is_timestamp=True)
                        elif table_name == 'smsapp_reportinfo' and col not in DATE_FIELDS.get(table_name, []):
                            value = handle_reportinfo_data(value)
                            
                        values.append(value)
                    batch_values.append(values)
                
                cursor.executemany(insert_query, batch_values)
                
            print(f"Successfully migrated {len(table_info['data'])} rows to {table_name}")
            
        except Exception as e:
            print(f"Error processing table {table_name}: {str(e)}")
            print("Continuing with next table...")
            continue
    
    connection.commit()
    connection.close()

if __name__ == "__main__":
    # PostgreSQL connection details - UPDATE THESE!
    PG_DB_NAME = 'adminmain'
    PG_USER = 'postgres'
    PG_PASSWORD = 'Solution@97'
    PG_HOST = '217.145.69.172'
    PG_PORT = '5432'
    
    # Path to the existing JSON backup file
    BACKUP_FILE = 'database_backup.json'
    
    print("Loading existing backup from JSON file...")
    backup_data = load_backup_from_json(BACKUP_FILE)
    
    if backup_data:
        print("Starting PostgreSQL restoration...")
        restore_to_postgres(
            backup_data,
            PG_DB_NAME,
            PG_USER,
            PG_PASSWORD,
            PG_HOST,
            PG_PORT
        )
        print("Migration completed!")
    else:
        print("Failed to load backup data. Migration aborted.")