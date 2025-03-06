import mysql.connector
import re
from typing import Dict, List, Tuple, Set
import os
import logging
from mysql.connector.pooling import MySQLConnectionPool
import time
from io import StringIO
import concurrent.futures

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection details
db_config = {
    "host": "localhost",
    "port": 3306,
    "user": "prashanth@itsolution4india.com",
    "password": "Solution@97",
    "database": "webhook_responses",
    "auth_plugin": 'mysql_native_password'
}

# Create a connection pool
pool = MySQLConnectionPool(pool_name="mypool", pool_size=5, **db_config)

def get_connection():
    return pool.get_connection()

def create_phone_specific_table(phone_number_id: str, cursor) -> str:
    """Create a table specific to a phone number ID if it doesn't exist."""
    table_name = f"webhook_responses_{phone_number_id}"
    
    # Check if table exists
    check_table_query = (
        f"SELECT COUNT(*) FROM information_schema.tables "
        f"WHERE table_schema = '{db_config['database']}' AND table_name = '{table_name}'"
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
    
    return table_name

def extract_phone_number_ids(sql_content: str) -> Set[str]:
    """Extract unique phone_number_ids from the SQL content."""
    # Regular expression to find phone_number_id values (assuming they're in the 3rd position)
    # This is much faster than parsing the entire SQL syntax
    pattern = r"VALUES\s*\([^,]+,[^,]+,\s*'([^']+)'"
    matches = re.findall(pattern, sql_content)
    return set(matches)

def create_tables_first(phone_ids: Set[str]):
    """Pre-create all tables for the phone_number_ids."""
    connection = get_connection()
    cursor = connection.cursor()
    
    try:
        for phone_id in phone_ids:
            create_phone_specific_table(phone_id, cursor)
        connection.commit()
        logger.info(f"Pre-created {len(phone_ids)} tables")
    finally:
        cursor.close()
        connection.close()

def process_sql_chunk(chunk: str):
    """Process a chunk of SQL statements."""
    connection = get_connection()
    cursor = connection.cursor()
    
    try:
        # Split SQL commands by semicolon
        sql_commands = chunk.strip().split(';')
        
        for command in sql_commands:
            command = command.strip()
            if not command:
                continue
            
            # Look for phone_number_id
            match = re.search(r"VALUES\s*\([^,]+,[^,]+,\s*'([^']+)'", command)
            if not match:
                continue
                
            phone_id = match.group(1)
            table_name = f"webhook_responses_{phone_id}"
            
            # Replace the table name
            modified_command = command.replace("`webhook_responses`", f"`{table_name}`")
            
            try:
                cursor.execute(modified_command)
            except mysql.connector.Error as err:
                logger.error(f"Error executing command: {err}")
                
        connection.commit()
    finally:
        cursor.close()
        connection.close()

def process_sql_file_in_chunks(filename: str, chunk_size: int = 10 * 1024 * 1024):
    """Process a large SQL file in chunks using a thread pool."""
    start_time = time.time()
    
    try:
        # First pass - extract all unique phone_number_ids and create tables
        logger.info("First pass - extracting phone IDs and creating tables...")
        with open(filename, 'r') as sql_file:
            sql_content = sql_file.read()
            
        phone_ids = extract_phone_number_ids(sql_content)
        logger.info(f"Found {len(phone_ids)} unique phone number IDs")
        
        create_tables_first(phone_ids)
        
        # Second pass - process data in chunks with multiple threads
        logger.info("Second pass - processing data in chunks...")
        chunks = []
        
        # Split the file into manageable chunks
        file_size = os.path.getsize(filename)
        num_chunks = (file_size // chunk_size) + 1
        logger.info(f"Processing file in {num_chunks} chunks")
        
        with open(filename, 'r') as sql_file:
            buffer = StringIO()
            lines_read = 0
            
            for line in sql_file:
                buffer.write(line)
                lines_read += 1
                
                if lines_read % 1000 == 0 and buffer.tell() >= chunk_size:
                    chunks.append(buffer.getvalue())
                    buffer = StringIO()
            
            # Add the last chunk if not empty
            if buffer.tell() > 0:
                chunks.append(buffer.getvalue())
        
        # Process chunks in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(process_sql_chunk, chunk) for chunk in chunks]
            
            # Wait for all futures to complete
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                logger.info(f"Completed chunk {i+1}/{len(chunks)}")
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error processing chunk: {e}")
        
        elapsed_time = time.time() - start_time
        logger.info(f"Completed SQL processing in {elapsed_time:.2f} seconds")
        
    except Exception as e:
        logger.error(f"Error processing SQL file: {e}")

# Main execution
if __name__ == "__main__":
    # Process the SQL file with optimized performance
    process_sql_file_in_chunks('webhook_responses02.sql')
    logger.info("SQL processing complete")