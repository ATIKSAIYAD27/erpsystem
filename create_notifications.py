import pymysql
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

def create_table():
    try:
        conn = pymysql.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            port=int(os.environ.get('DB_PORT', 3306)),
            user=os.environ.get('DB_USER', 'root'),
            password=os.environ.get('DB_PASSWORD', ''),
            database=os.environ.get('DB_NAME', 'erpsystem')
        )
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    message TEXT NOT NULL,
                    type VARCHAR(20) DEFAULT 'info',
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)
            
            # Add some initial notifications for the admin
            cursor.execute("SELECT user_id FROM users WHERE role_id = (SELECT role_id FROM roles WHERE role_name = 'Admin') LIMIT 1")
            admin = cursor.fetchone()
            if admin:
                cursor.execute("INSERT INTO notifications (user_id, message, type) VALUES (%s, 'System Phase 4 is now active!', 'info')", (admin[0],))
                cursor.execute("INSERT INTO notifications (user_id, message, type) VALUES (%s, 'Alert: Check inventory for low stock items.', 'warning')", (admin[0],))
            
        conn.commit()
        print("Notifications table created successfully!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    create_table()
