import psycopg2
import re

def restore_sql_backup(sql_file, db_config):
    """Restore data from SQL backup file to PostgreSQL database"""
    conn = None
    cursor = None
    
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            dbname=db_config['NAME'],
            user=db_config['USER'],
            password=db_config['PASSWORD'],
            host=db_config['HOST'],
            port=db_config['PORT']
        )
        cursor = conn.cursor()

        # Read the SQL file
        print("Reading SQL file...")
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # Replace AUTOINCREMENT with SERIAL
        sql_content = re.sub(
            r'PRIMARY KEY\s*\(\s*"?(\w+)"?\s+AUTOINCREMENT\s*\)',
            r'PRIMARY KEY ("\1"), "\1" SERIAL',
            sql_content,
            flags=re.IGNORECASE
        )

        # Ensure the created_at is treated properly as a timestamp in SQL
        sql_content = re.sub(
            r'"created_at"\s+datetime',
            r'"created_at" timestamp',
            sql_content
        )
        
        # Start transaction
        print("Processing SQL statements...")
        cursor.execute("BEGIN;")
        
        # Temporarily disable triggers to prevent automatic timestamp updates
        cursor.execute("""
            DO $$
            BEGIN
                EXECUTE (
                    SELECT string_agg(
                        format('ALTER TABLE %I.%I DISABLE TRIGGER ALL', schemaname, tablename),
                        '; '
                    )
                    FROM pg_tables
                    WHERE schemaname = 'public'
                );
            END $$;
        """)
        
        # Set timezone to UTC to ensure consistent timestamp handling
        cursor.execute("SET TIME ZONE 'UTC';")
        
        # Execute the SQL content
        cursor.execute(sql_content)
        
        # Re-enable triggers
        cursor.execute("""
            DO $$
            BEGIN
                EXECUTE (
                    SELECT string_agg(
                        format('ALTER TABLE %I.%I ENABLE TRIGGER ALL', schemaname, tablename),
                        '; '
                    )
                    FROM pg_tables
                    WHERE schemaname = 'public'
                );
            END $$;
        """)
        
        # Commit the transaction
        conn.commit()
        print("Backup restoration completed successfully!")
        
    except Exception as e:
        print(f"Error during restoration: {str(e)}")
        if conn:
            conn.rollback()
            print("Changes rolled back due to error")
            
            # Try to re-enable triggers in case of error
            try:
                cursor.execute("BEGIN;")
                cursor.execute("""
                    DO $$
                    BEGIN
                        EXECUTE (
                            SELECT string_agg(
                                format('ALTER TABLE %I.%I ENABLE TRIGGER ALL', schemaname, tablename),
                                '; '
                            )
                            FROM pg_tables
                            WHERE schemaname = 'public'
                        );
                    END $$;
                """)
                conn.commit()
            except:
                print("Warning: Failed to re-enable triggers after error")
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            print("Database connection closed")

if __name__ == "__main__":
    # Database configuration
    db_config = {
        'NAME': 'admin',
        'USER': 'itsolutions',
        'PASSWORD': 'Solution@97',
        'HOST': '217.145.69.172',
        'PORT': '5432'
    }
    
    # SQL backup file path
    sql_file = 'smsapp_reportinfo.sql'
    
    # Restore backup
    print(f"Starting restoration from {sql_file}...")
    restore_sql_backup(sql_file, db_config)
