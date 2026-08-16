from app.db import get_db_connection
from functools import wraps
from flask import session, redirect, url_for, flash
import datetime as _dt
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def get_db():
    """Safe database connection context manager with automatic cleanup."""
    conn = get_db_connection()
    try:
        yield conn
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def safe_int(value, default=0):
    """Safely cast to int, returning default on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value, default=0.0):
    """Safely cast to float, returning default on failure."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def amount_in_words(amount):
    """Convert a numeric amount to Indian currency words."""
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return "Zero Rupees Only"

    if amount < 0:
        return "Minus " + amount_in_words(-amount)

    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven",
            "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
            "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty",
            "Seventy", "Eighty", "Ninety"]

    def _convert_below_thousand(n):
        if n == 0:
            return ""
        elif n < 20:
            return ones[n]
        elif n < 100:
            return (tens[n // 10] + " " + ones[n % 10]).strip()
        else:
            return (ones[n // 100] + " Hundred " + _convert_below_thousand(n % 100)).strip()

    int_part = int(amount)
    dec_part = round((amount - int_part) * 100)

    if int_part == 0 and dec_part == 0:
        return "Zero Rupees Only"

    result = ""
    if int_part >= 10000000:
        result += _convert_below_thousand(int_part // 10000000) + " Crore "
        int_part %= 10000000
    if int_part >= 100000:
        result += _convert_below_thousand(int_part // 100000) + " Lakh "
        int_part %= 100000
    if int_part >= 1000:
        result += _convert_below_thousand(int_part // 1000) + " Thousand "
        int_part %= 1000
    if int_part > 0:
        result += _convert_below_thousand(int_part) + " "

    result = result.strip() + " Rupees"
    if dec_part > 0:
        result += " and " + _convert_below_thousand(dec_part) + " Paise"
    result += " Only"
    return result


def indian_currency(amount):
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
    if date_val is None:
        return ''
    if isinstance(date_val, str):
        try:
            date_val = _dt.datetime.strptime(date_val, '%Y-%m-%d').date()
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
        try:
            from app import socketio
            socketio.emit('new_notification', {
                'message': message,
                'type': msg_type,
                'timestamp': str(_dt.datetime.now())
            }, room=f"user_{user_id}")
        except Exception:
            pass
        return True
    except Exception as e:
        logger.error("Error creating notification: %s", e)
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
        try:
            from app import socketio
            socketio.emit('new_notification', {
                'message': message,
                'type': msg_type,
                'timestamp': str(_dt.datetime.now())
            }, room='admins')
        except Exception:
            pass
        return True
    except Exception as e:
        logger.error("Error notifying admins: %s", e)
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
        logger.error("Error logging audit: %s", e)


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
