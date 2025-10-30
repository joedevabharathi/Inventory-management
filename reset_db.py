import pymysql

def execute_sql_file(connection, sql_file):
    with open(sql_file, 'r') as file:
        sql = file.read()
        
    with connection.cursor() as cursor:
        # Split SQL commands by semicolon and execute each one
        for command in sql.split(';'):
            if command.strip():
                cursor.execute(command)
    connection.commit()

# Database connection without database
connection = pymysql.connect(
    host='127.0.0.1',
    user='root',
    password='2003'
)

try:
    with connection.cursor() as cursor:
        # Drop and recreate database
        cursor.execute("DROP DATABASE IF EXISTS inventory_db")
        cursor.execute("CREATE DATABASE inventory_db")
        cursor.execute("USE inventory_db")
        print("Database recreated successfully")
        
        # Execute the schema file
        execute_sql_file(connection, 'new_schema.sql')
        print("Schema executed successfully")
        
        # Verify the structure
        cursor.execute("DESCRIBE locations")
        print("\nLocations table structure:")
        for column in cursor.fetchall():
            print(column)

finally:
    connection.close()
    print("Database connection closed")