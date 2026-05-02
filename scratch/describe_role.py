import os
from dotenv import load_dotenv
import pymysql

load_dotenv()

try:
    conn = pymysql.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=int(os.environ.get('DB_PORT', 3307)),
        user=os.environ.get('DB_USER', 'root'),
        password=os.environ.get('DB_PASSWORD', ''),
        database=os.environ.get('DB_NAME', 'erpsystem')
    )
    with conn.cursor() as cursor:
        cursor.execute('DESCRIBE role')
        schema = cursor.fetchall()
        for col in schema:
            print(col)
    conn.close()
except Exception as e:
    print(f"Error: {e}")
