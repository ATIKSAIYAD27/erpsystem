import pymysql

DB_CONFIG = {
    'host': 'localhost',
    'port': 3307,
    'user': 'root',
    'password': '',
    'database': 'erpsystem',
    'cursorclass': pymysql.cursors.DictCursor
}

def check_notifications():
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            cursor.execute("DESCRIBE notifications")
            columns = cursor.fetchall()
            print("Notifications Table Schema:")
            for col in columns:
                print(col)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_notifications()
