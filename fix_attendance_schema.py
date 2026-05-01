import pymysql
from app.db import DB_CONFIG

def fix_schema():
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Add ip_address to audit_log
        try:
            cursor.execute("ALTER TABLE audit_log ADD COLUMN ip_address VARCHAR(45)")
            print("Successfully added ip_address to audit_log")
        except Exception as e:
            print(f"audit_log column check: {e}")

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_schema()
