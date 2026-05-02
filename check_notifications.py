import pymysql
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

def check_notifications():
    try:
        conn = pymysql.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            port=int(os.environ.get('DB_PORT', 3306)),
            user=os.environ.get('DB_USER', 'root'),
            password=os.environ.get('DB_PASSWORD', ''),
            database=os.environ.get('DB_NAME', 'erpsystem'),
            cursorclass=pymysql.cursors.DictCursor
        )
        with conn.cursor() as cursor:
            cursor.execute("DESCRIBE notifications")
            columns = cursor.fetchall()
            print("Notifications Table Schema:")
            for col in columns:
                print(col)
            
            cursor.execute("SELECT COUNT(*) as count FROM notifications")
            count = cursor.fetchone()['count']
            print(f"\nTotal notifications in table: {count}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_notifications()
