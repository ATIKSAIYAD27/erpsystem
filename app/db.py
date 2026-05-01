import pymysql
import os
from dotenv import load_dotenv

# Load .env file for local development
load_dotenv()

def get_db_connection():
    # Railway provides separate variables or a URL. 
    # We will prioritize env variables, and fallback to defaults if not set.
    return pymysql.connect(
        host=os.environ.get('DB_HOST', os.environ.get('MYSQLHOST', 'localhost')),
        port=int(os.environ.get('DB_PORT', os.environ.get('MYSQLPORT', 3306))),
        user=os.environ.get('DB_USER', os.environ.get('MYSQLUSER', 'root')),
        password=os.environ.get('DB_PASSWORD', os.environ.get('MYSQLPASSWORD', '')),
        database=os.environ.get('DB_NAME', os.environ.get('MYSQLDATABASE', 'erpsystem')),
        cursorclass=pymysql.cursors.DictCursor
    )
