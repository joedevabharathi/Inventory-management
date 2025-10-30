import pymysql

# Database connection
connection = pymysql.connect(
    host='127.0.0.1',
    user='root',
    password='2003',
    database='inventory_db'
)

try:
    with connection.cursor() as cursor:
        # Check table structure
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print("Tables in database:", tables)
        
        # Check locations table structure
        cursor.execute("DESCRIBE locations")
        columns = cursor.fetchall()
        print("\nLocations table structure:")
        for column in columns:
            print(column)

finally:
    connection.close()