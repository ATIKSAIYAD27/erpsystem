from app.db import get_db_connection
import pymysql

def check_notif_schema():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DESCRIBE notifications")
            columns = cursor.fetchall()
            for col in columns:
                print(col)
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_notif_schema()
