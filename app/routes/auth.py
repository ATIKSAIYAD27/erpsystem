from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
import re
import logging
import secrets
import datetime

auth_bp = Blueprint('auth', __name__)

logger = logging.getLogger(__name__)

from app.db import get_db_connection


def _validate_password(password):
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r'[A-Z]', password):
        return "Password must contain at least one uppercase letter."
    if not re.search(r'[a-z]', password):
        return "Password must contain at least one lowercase letter."
    if not re.search(r'\d', password):
        return "Password must contain at least one digit."
    if not re.search(r'[!@#$%^&*(),.?\":{}|<>]', password):
        return "Password must contain at least one special character."
    return None


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('Please enter both email and password.', 'danger')
            return render_template('login.html')

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                try:
                    sql = """
                        SELECT u.user_id, u.name, u.email, u.password_hash, u.role_id, r.role_name,
                               u.totp_enabled
                        FROM users u
                        LEFT JOIN role r ON u.role_id = r.role_id
                        WHERE u.email = %s
                    """
                    cursor.execute(sql, (email,))
                    user = cursor.fetchone()
                except Exception:
                    sql = """
                        SELECT u.user_id, u.name, u.email, u.password_hash, u.role_id, r.role_name
                        FROM users u
                        LEFT JOIN role r ON u.role_id = r.role_id
                        WHERE u.email = %s
                    """
                    cursor.execute(sql, (email,))
                    user = cursor.fetchone()
                    if user:
                        user['totp_enabled'] = 0
            conn.close()

            if user and check_password_hash(user['password_hash'], password):
                if user.get('totp_enabled'):
                    session['pre_2fa_user_id'] = user['user_id']
                    return redirect(url_for('twofa.verify'))

                session['user_id'] = user['user_id']
                session['role_id'] = user['role_id']
                session['name'] = user['name'] or 'User'
                session['role_name'] = user['role_name'] or 'Employee'
                session.permanent = True
                return redirect(url_for('dashboard.dashboard'))
            else:
                flash('Invalid email or password.', 'danger')

        except Exception as e:
            logger.error("Login error: %s", e)
            flash('An unexpected error occurred. Please try again.', 'danger')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        if not all([name, email, password]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('auth.register'))

        pw_error = _validate_password(password)
        if pw_error:
            flash(pw_error, 'danger')
            return redirect(url_for('auth.register'))

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
                if cursor.fetchone():
                    flash('Email already registered.', 'warning')
                    return redirect(url_for('auth.register'))

                cursor.execute("SELECT role_id FROM role WHERE role_name = 'Employee'")
                emp_role = cursor.fetchone()
                role_id = emp_role['role_id'] if emp_role else 3

                hashed_pw = generate_password_hash(password)
                cursor.execute(
                    "INSERT INTO users (name, email, password_hash, role_id) VALUES (%s, %s, %s, %s)",
                    (name, email, hashed_pw, role_id)
                )

            conn.commit()
            conn.close()

            try:
                from app.utils import notify_admin
                notify_admin(f"New user registered: {name} ({email})", 'info')
            except Exception as notify_err:
                logger.warning("Failed to notify admin: %s", notify_err)

            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            logger.error("Registration error: %s", e)
            flash('An unexpected error occurred. Please try again.', 'danger')

    return render_template('register.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            flash('Please enter your email address.', 'danger')
            return render_template('forgot_password.html')

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT user_id, email FROM users WHERE email = %s", (email,))
                user = cursor.fetchone()

                if user:
                    token = secrets.token_urlsafe(32)
                    expiry = datetime.datetime.now() + datetime.timedelta(hours=1)

                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS password_reset_token (
                            id SERIAL PRIMARY KEY,
                            user_id INT NOT NULL,
                            token VARCHAR(128) NOT NULL UNIQUE,
                            expires_at TIMESTAMP NOT NULL,
                            used BOOLEAN DEFAULT FALSE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                        )
                    """)
                    cursor.execute("DELETE FROM password_reset_token WHERE user_id = %s", (user['user_id'],))
                    cursor.execute("""
                        INSERT INTO password_reset_token (user_id, token, expires_at)
                        VALUES (%s, %s, %s)
                    """, (user['user_id'], token, expiry))

                    from app.utils import create_notification
                    create_notification(user['user_id'],
                        f"Password reset requested. Use token: {token[:8]}... (valid 1 hour)",
                        'warning')

            conn.commit()
            conn.close()
            flash('If an account exists with that email, a reset token has been generated. Check your notifications.', 'info')
        except Exception as e:
            logger.error("Forgot password error: %s", e)
            flash('An unexpected error occurred.', 'danger')

        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not token or not new_password:
            flash('All fields are required.', 'danger')
            return render_template('reset_password.html')

        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html')

        pw_error = _validate_password(new_password)
        if pw_error:
            flash(pw_error, 'danger')
            return render_template('reset_password.html')

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, user_id, expires_at FROM password_reset_token
                    WHERE token = %s AND used = FALSE
                """, (token,))
                reset_record = cursor.fetchone()

                if not reset_record:
                    flash('Invalid or expired reset token.', 'danger')
                    return render_template('reset_password.html')

                if datetime.datetime.now() > reset_record['expires_at']:
                    flash('Reset token has expired. Please request a new one.', 'danger')
                    return render_template('reset_password.html')

                hashed_pw = generate_password_hash(new_password)
                cursor.execute("UPDATE users SET password_hash = %s WHERE user_id = %s",
                              (hashed_pw, reset_record['user_id']))
                cursor.execute("UPDATE password_reset_token SET used = TRUE WHERE id = %s",
                              (reset_record['id'],))

            conn.commit()
            conn.close()
            flash('Password reset successful! Please login with your new password.', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            logger.error("Reset password error: %s", e)
            flash('An unexpected error occurred.', 'danger')

    return render_template('reset_password.html')
