from app.db import get_db_connection

def seed_notifs():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Check if any admin exists
            cursor.execute("SELECT user_id FROM users LIMIT 5")
            users = cursor.fetchall()
            
            for user in users:
                user_id = user['user_id']
                # Add a welcome notification if not present
                cursor.execute("SELECT id FROM notifications WHERE user_id = %s LIMIT 1", (user_id,))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO notifications (user_id, message, type) 
                        VALUES (%s, 'Welcome to Nexus ERP! Your system is now AI-enabled.', 'success')
                    """, (user_id,))
                    cursor.execute("""
                        INSERT INTO notifications (user_id, message, type) 
                        VALUES (%s, 'Phase 4 Update: PDF Reports and Notifications are now active.', 'info')
                    """, (user_id,))
            
        conn.commit()
        conn.close()
        print("Notifications seeded successfully!")
    except Exception as e:
        print(f"Error seeding: {e}")

if __name__ == "__main__":
    seed_notifs()
