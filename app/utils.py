from app.db import get_db_connection

def create_notification(user_id, message, msg_type='info'):
    """
    Creates a notification for a specific user.
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO notifications (user_id, message, type) VALUES (%s, %s, %s)",
                (user_id, message, msg_type)
            )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error creating notification: {e}")
        return False

def notify_admin(message, msg_type='info'):
    """
    Creates a notification for all admin users.
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Find all admin users
            cursor.execute("SELECT user_id FROM users WHERE role_id = (SELECT role_id FROM role WHERE role_name = 'Admin')")
            admins = cursor.fetchall()
            for admin in admins:
                cursor.execute(
                    "INSERT INTO notifications (user_id, message, type) VALUES (%s, %s, %s)",
                    (admin['user_id'], message, msg_type)
                )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error notifying admins: {e}")
        return False
