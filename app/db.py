import pymysql
import os
import logging
from dotenv import load_dotenv
from dbutils.pooled_db import PooledDB

load_dotenv()

logger = logging.getLogger(__name__)

_pool = None

MAX_RETRIES = 3
RETRY_DELAY = 0.5


class ManagedCursor:
    """Cursor wrapper that auto-closes parent connection when cursor context exits."""

    def __init__(self, conn_wrapper):
        self._conn_wrapper = conn_wrapper
        self._cursor = conn_wrapper._conn.cursor()

    def __enter__(self):
        return self._cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self._cursor.close()
        except Exception:
            pass
        if exc_type is not None:
            try:
                self._conn_wrapper._conn.rollback()
            except Exception:
                pass
        try:
            self._conn_wrapper._conn.close()
        except Exception:
            pass
        return False

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class ManagedConnection:
    """Wraps a DB connection with automatic cleanup."""

    def __init__(self, conn):
        self._conn = conn
        self._committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None and not self._committed:
                try:
                    self._conn.rollback()
                except Exception:
                    pass
            self._conn.close()
        except Exception:
            pass
        return False

    def cursor(self, cursor=None):
        return ManagedCursor(self)

    def commit(self):
        self._committed = True
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass


def _get_pool():
    global _pool
    if _pool is None:
        host = os.environ.get('DB_HOST', os.environ.get('MYSQLHOST', '127.0.0.1'))
        port = int(os.environ.get('DB_PORT', os.environ.get('MYSQLPORT', 3306)))
        user = os.environ.get('DB_USER', os.environ.get('MYSQLUSER', 'root'))
        password = os.environ.get('DB_PASSWORD', os.environ.get('MYSQLPASSWORD', ''))
        database = os.environ.get('DB_NAME', os.environ.get('MYSQLDATABASE', 'erpsystem'))

        ssl_config = None
        mysql_ssl_ca = os.environ.get('MYSQL_ROOT_CERT')
        if mysql_ssl_ca:
            ssl_config = {'ca': mysql_ssl_ca}

        _pool = PooledDB(
            creator=pymysql,
            maxconnections=20,
            mincached=2,
            maxcached=10,
            blocking=True,
            maxusage=None,
            setsession=["SET NAMES utf8mb4", "SET SESSION wait_timeout=28800"],
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
            charset='utf8mb4',
            ssl=ssl_config if ssl_config else None,
        )
        logger.info("Database connection pool initialized (max=%d)", 20)
    return _pool


def get_db_connection():
    """Returns a ManagedConnection that auto-closes when used with 'with' or .cursor()."""
    import time
    pool = _get_pool()
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            conn = pool.connection()
            return ManagedConnection(conn)
        except Exception as e:
            last_error = e
            logger.warning("DB connection attempt %d failed: %s", attempt + 1, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    logger.error("Failed to get connection from pool after %d retries: %s", MAX_RETRIES, last_error)
    raise last_error


def close_connection(conn):
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
