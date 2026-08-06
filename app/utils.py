from app.db import get_db_connection
from functools import wraps
from flask import session, redirect, url_for, flash
import datetime


def indian_currency(amount):
    """Format number in Indian currency style: Rs. 1,00,000.00"""
    if amount is None:
        return 'Rs. 0.00'
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return 'Rs. 0.00'
    negative = amount < 0
    amount = abs(amount)
    s = f"{amount:.2f}"
    integer_part, decimal_part = s.split('.')
    n = len(integer_part)
    if n <= 3:
        formatted = integer_part
    else:
        last3 = integer_part[-3:]
        remaining = integer_part[:-3]
        parts = []
        while len(remaining) > 2:
            parts.append(remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            parts.append(remaining)
        parts.reverse()
        formatted = ','.join(parts) + ',' + last3
    result = f"Rs. {formatted}.{decimal_part}"
    return f"-{result}" if negative else result


def indian_number(amount):
    """Format number in Indian style without currency symbol: 1,00,000"""
    if amount is None:
        return '0'
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return '0'
    negative = amount < 0
    amount = abs(amount)
    s = f"{amount:.2f}"
    integer_part, decimal_part = s.split('.')
    n = len(integer_part)
    if n <= 3:
        formatted = integer_part
    else:
        last3 = integer_part[-3:]
        remaining = integer_part[:-3]
        parts = []
        while len(remaining) > 2:
            parts.append(remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            parts.append(remaining)
        parts.reverse()
        formatted = ','.join(parts) + ',' + last3
    result = f"{formatted}.{decimal_part}"
    return f"-{result}" if negative else result


def indian_date(date_val):
    """Format date as DD/MM/YYYY (Indian standard)"""
    if date_val is None:
        return ''
    if isinstance(date_val, str):
        try:
            date_val = datetime.datetime.strptime(date_val, '%Y-%m-%d').date()
        except ValueError:
            return date_val
    return date_val.strftime('%d/%m/%Y')

def create_notification(user_id, message, msg_type='info'):
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
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
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

def log_audit(user_id, action, ip_address=None):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO audit_log (user_id, action, ip_address) VALUES (%s, %s, %s)",
                (user_id, action, ip_address)
            )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging audit: {e}")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('role_name') != 'Admin':
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('dashboard.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def manager_or_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('role_name') not in ('Admin', 'Manager'):
            flash('Access denied. Manager or Admin privileges required.', 'danger')
            return redirect(url_for('dashboard.dashboard'))
        return f(*args, **kwargs)
    return decorated_function
