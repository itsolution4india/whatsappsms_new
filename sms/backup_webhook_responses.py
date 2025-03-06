import mysql.connector
import re
from typing import Dict, List, Tuple
import os
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection details
db_connection = mysql.connector.connect(
    host="localhost",
    port=3306,
    user="prashanth@itsolution4india.com",
    password="Solution@97",
    database="webhook_responses",
    auth_plugin='mysql_native_password'
)

def create_phone_specific_table(phone_number_id: str, cursor) -> None:
    """Create a table specific to a phone number ID if it doesn't exist."""
    table_name = f"webhook_responses_{phone_number_id}"
    
    # Check if table exists
    check_table_query = (
        f"SELECT COUNT(*) FROM information_schema.tables "
        f"WHERE table_schema = 'webhook_responses' AND table_name = '{table_name}'"
    )
    cursor.execute(check_table_query)
    table_exists = cursor.fetchone()[0] > 0
    
    if not table_exists:
        # Create table with the specified fields
        create_table_query = f"""
        CREATE TABLE {table_name} (
            id INT AUTO_INCREMENT PRIMARY KEY,
            `Date` datetime NOT NULL,
            `display_phone_number` varchar(255) DEFAULT NULL,
            `phone_number_id` varchar(255) DEFAULT NULL,
            `waba_id` varchar(255) DEFAULT NULL,
            `contact_wa_id` varchar(255) DEFAULT NULL,
            `status` varchar(50) DEFAULT NULL,
            `message_timestamp` varchar(50) DEFAULT NULL,
            `error_code` int DEFAULT NULL,
            `error_message` text,
            `contact_name` varchar(255) DEFAULT NULL,
            `message_from` varchar(255) DEFAULT NULL,
            `message_type` varchar(50) DEFAULT NULL,
            `message_body` text
        )
        """
        cursor.execute(create_table_query)
        db_connection.commit()
        logger.info(f"Created new table: {table_name}")
    
    return table_name

def parse_insert_statements(sql_content: str) -> List[Tuple[str, str]]:
    """
    Parse INSERT statements from SQL file and extract phone_number_id 
    and the complete INSERT statement.
    """
    # Regular expression to find INSERT statements
    insert_pattern = r"INSERT INTO\s+`webhook_responses`\s+\([^)]+\)\s+VALUES\s+([^;]+)"
    
    # Find all insert statements
    insert_statements = re.findall(insert_pattern, sql_content)
    
    results = []
    for statement in insert_statements:
        # Extract all value sets
        values_pattern = r"\(([^)]+)\)"
        value_sets = re.findall(values_pattern, statement)
        
        for value_set in value_sets:
            # Split the values
            values = [v.strip() for v in value_set.split(',')]
            
            # Check we have enough values (phone_number_id should be the 3rd item)
            if len(values) >= 3:
                # Extract phone_number_id (removing quotes if present)
                phone_number_id = values[2].strip("'\"")
                
                # Reconstruct the insert with just this value set
                insert_sql = f"INSERT INTO `placeholder_table` (`Date`, `display_phone_number`, `phone_number_id`, `waba_id`, `contact_wa_id`, `status`, `message_timestamp`, `error_code`, `error_message`, `contact_name`, `message_from`, `message_type`, `message_body`) VALUES ({value_set})"
                
                results.append((phone_number_id, insert_sql))
    
    return results

def execute_sql_file(filename: str) -> None:
    """Read and execute SQL file, creating phone-specific tables."""
    try:
        with open(filename, 'r') as sql_file:
            sql_content = sql_file.read()
        
        # Parse the INSERT statements and extract phone_number_id
        insert_data = parse_insert_statements(sql_content)
        
        # Create a cursor
        cursor = db_connection.cursor()
        
        # Process each INSERT statement
        tables_created = set()
        for phone_number_id, insert_sql in insert_data:
            try:
                # Create table specific to this phone_number_id if needed
                table_name = create_phone_specific_table(phone_number_id, cursor)
                
                if table_name not in tables_created:
                    tables_created.add(table_name)
                
                # Replace placeholder with actual table name
                insert_sql = insert_sql.replace("placeholder_table", table_name)
                
                # Execute the INSERT
                cursor.execute(insert_sql)
                db_connection.commit()
                logger.info(f"Inserted data into {table_name}")
                
            except mysql.connector.Error as err:
                logger.error(f"Error: {err}")
                db_connection.rollback()
        
        cursor.close()
        logger.info(f"Created {len(tables_created)} tables and processed {len(insert_data)} records")
        
    except FileNotFoundError:
        logger.error(f"File not found: {filename}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

# Call the function to execute SQL file
if __name__ == "__main__":
    execute_sql_file('webhook_responses04.sql')
    
    # Close the database connection
    db_connection.close()
    logger.info("Database connection closed")