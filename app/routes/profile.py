from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from app.db import get_db_connection
from app.utils import login_required
import re
import logging

profile_bp = Blueprint('profile', __name__)

logger = logging.getLogger(__name__)


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


@profile_bp.route('/settings')
@login_required
def index():
    user_id = session['user_id']
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
        conn.close()
        return render_template('profile.html', user=user)
    except Exception as e:
        logger.error("Profile error: %s", e)
        flash('An unexpected error occurred.', 'danger')
        return redirect(url_for('dashboard.dashboard'))


@profile_bp.route('/settings/update', methods=['POST'])
@login_required
def update_profile():
    user_id = session['user_id']
    name = request.form.get('name')
    email = request.form.get('email')
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if new_password:
                if not current_password:
                    flash('Current password is required to set a new password.', 'danger')
                    return redirect(url_for('profile.index'))

                cursor.execute("SELECT password_hash FROM users WHERE user_id = %s", (user_id,))
                user = cursor.fetchone()
                if not user or not check_password_hash(user['password_hash'], current_password):
                    flash('Current password is incorrect.', 'danger')
                    return redirect(url_for('profile.index'))

                pw_error = _validate_password(new_password)
                if pw_error:
                    flash(pw_error, 'danger')
                    return redirect(url_for('profile.index'))

                hashed_password = generate_password_hash(new_password)
                cursor.execute("UPDATE users SET name=%s, email=%s, password_hash=%s WHERE user_id=%s", (name, email, hashed_password, user_id))
            else:
                cursor.execute("UPDATE users SET name=%s, email=%s WHERE user_id=%s", (name, email, user_id))
        conn.commit()
        conn.close()
        session['name'] = name
        flash('Profile updated successfully!', 'success')
    except Exception as e:
        logger.error("Update profile error: %s", e)
        flash('An unexpected error occurred.', 'danger')

    return redirect(url_for('profile.index'))
