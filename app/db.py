import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    host = os.environ.get('DB_HOST', os.environ.get('MYSQLHOST', '127.0.0.1'))
    port = int(os.environ.get('DB_PORT', os.environ.get('MYSQLPORT', 3306)))
    user = os.environ.get('DB_USER', os.environ.get('MYSQLUSER', 'root'))
    password = os.environ.get('DB_PASSWORD', os.environ.get('MYSQLPASSWORD', ''))
    database = os.environ.get('DB_NAME', os.environ.get('MYSQLDATABASE', 'erpsystem'))

    try:
        return pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5
        )
    except Exception as primary_error:
        fallback_host = None
        if host == '127.0.0.1':
            fallback_host = 'localhost'
        elif host == 'localhost':
            fallback_host = '127.0.0.1'

        if fallback_host:
            try:
                return pymysql.connect(
                    host=fallback_host,
                    port=port,
                    user=user,
                    password=password,
                    database=database,
                    cursorclass=pymysql.cursors.DictCursor,
                    connect_timeout=5
                )
            except Exception:
                pass

        raise primary_error
