import mysql.connector

# Database connection details
db_connection = mysql.connector.connect(
    host="localhost",
    port=3306,
    user="prashanth@itsolution4india.com",
    password="Solution@97",
    database="webhook_responses",
    auth_plugin='mysql_native_password'
)

# Read the SQL file
def execute_sql_file(filename):
    with open(filename, 'r') as sql_file:
        sql_commands = sql_file.read()

    # Split SQL commands by semicolon
    sql_commands = sql_commands.split(';')

    # Create a cursor object to interact with the database
    cursor = db_connection.cursor()

    # Execute each SQL command
    for command in sql_commands:
        command = command.strip()
        if command:  # Make sure the command is not empty
            try:
                cursor.execute(command)
                db_connection.commit()
                print(f"Executed: {command}")
            except mysql.connector.Error as err:
                print(f"Error: {err}")
                db_connection.rollback()

    cursor.close()

# Call the function to execute SQL file.
if __name__ == "__main__":
    execute_sql_file('webhook_responses03.sql')

# Close the database connection
db_connection.close()
