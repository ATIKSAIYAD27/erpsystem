from app.db import get_db_connection
import os
from dotenv import load_dotenv

load_dotenv()
print(f"DB_HOST: {os.environ.get('DB_HOST')}")
print(f"DB_PORT: {os.environ.get('DB_PORT')}")

try:
    conn = get_db_connection()
    print("Connection successful!")
    conn.close()
except Exception as e:
    print(f"Connection failed: {e}")
