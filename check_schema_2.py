from app.db import get_db_connection
import pymysql

def check_schemas():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            for table in ['sale', 'attendance']:
                print(f"--- {table} ---")
                cursor.execute(f"DESCRIBE {table}")
                columns = cursor.fetchall()
                for col in columns:
                    print(col)
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_schemas()
