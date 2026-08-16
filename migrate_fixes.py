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
    return pymysql.connect(
        host=host, port=port, user=user, password=password,
        database=database, cursorclass=pymysql.cursors.DictCursor, connect_timeout=5
    )


def migrate():
    print("Running comprehensive migration (fixes)...")

    conn = get_db_connection()
    with conn.cursor() as cursor:

        migrations = [
            ("ALTER TABLE expense ADD COLUMN department VARCHAR(100) DEFAULT 'General' AFTER category",
             "Added department column to expense table"),
        ]

        for sql, description in migrations:
            try:
                cursor.execute(sql)
                print(f"  [OK] {description}")
            except Exception as e:
                if "Duplicate column" in str(e):
                    print(f"  [SKIP] {description} (already exists)")
                else:
                    print(f"  [WARN] {description}: {e}")

        try:
            cursor.execute("ALTER TABLE expense MODIFY COLUMN department VARCHAR(100) DEFAULT 'General'")
            print("  [OK] Modified department column to have DEFAULT 'General'")
        except Exception as e:
            print(f"  [SKIP] department column modification: {e}")

    conn.commit()
    conn.close()
    print("Comprehensive migration complete!")


if __name__ == "__main__":
    migrate()
