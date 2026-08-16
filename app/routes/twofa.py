from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash
import pyotp
import qrcode
import io
import base64
import logging
from app.db import get_db_connection
from app.utils import login_required

twofa_bp = Blueprint('twofa', __name__)
logger = logging.getLogger(__name__)


def _get_user_2fa_secret(user_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT totp_secret, totp_enabled FROM users WHERE user_id = %s", (user_id,))
            row = cursor.fetchone()
        conn.close()
        return row
    except Exception as e:
        logger.error("Error fetching 2FA secret: %s", e)
        return None


@twofa_bp.route('/2fa/setup', methods=['GET', 'POST'])
@login_required
def setup():
    user_id = session['user_id']
    user_2fa = _get_user_2fa_secret(user_id)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'enable':
            password = request.form.get('password')
            totp_code = request.form.get('totp_code')
            secret = request.form.get('secret')

            if not password or not totp_code or not secret:
                flash('All fields are required.', 'danger')
                return redirect(url_for('twofa.setup'))

            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT password_hash FROM users WHERE user_id = %s", (user_id,))
                user = cursor.fetchone()
            conn.close()

            if not user or not check_password_hash(user['password_hash'], password):
                flash('Incorrect password.', 'danger')
                return redirect(url_for('twofa.setup'))

            totp = pyotp.TOTP(secret)
            if not totp.verify(totp_code, valid_window=1):
                flash('Invalid verification code. Please try again.', 'danger')
                session['pending_2fa_secret'] = secret
                qr = _generate_qr(secret, session.get('name', 'User'), session.get('email', ''))
                return render_template('twofa_setup.html', secret=secret, qr_code=qr, pending=True)

            try:
                conn = get_db_connection()
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE users SET totp_secret=%s, totp_enabled=1 WHERE user_id=%s",
                        (secret, user_id)
                    )
                conn.commit()
                conn.close()
                flash('Two-factor authentication enabled successfully!', 'success')
                session.pop('pending_2fa_secret', None)
                return redirect(url_for('twofa.setup'))
            except Exception as e:
                logger.error("Error enabling 2FA: %s", e)
                flash('An error occurred.', 'danger')

        elif action == 'disable':
            password = request.form.get('password')
            if not password:
                flash('Password is required to disable 2FA.', 'danger')
                return redirect(url_for('twofa.setup'))

            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT password_hash FROM users WHERE user_id = %s", (user_id,))
                user = cursor.fetchone()
            conn.close()

            if not user or not check_password_hash(user['password_hash'], password):
                flash('Incorrect password.', 'danger')
                return redirect(url_for('twofa.setup'))

            try:
                conn = get_db_connection()
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE users SET totp_secret=NULL, totp_enabled=0 WHERE user_id=%s",
                        (user_id,)
                    )
                conn.commit()
                conn.close()
                flash('Two-factor authentication disabled.', 'warning')
                return redirect(url_for('twofa.setup'))
            except Exception as e:
                logger.error("Error disabling 2FA: %s", e)
                flash('An error occurred.', 'danger')

    secret = session.get('pending_2fa_secret') or (user_2fa and user_2fa.get('totp_secret')) or pyotp.random_base32()
    if not user_2fa or not user_2fa.get('totp_enabled'):
        session['pending_2fa_secret'] = secret

    qr = _generate_qr(secret, session.get('name', 'User'), session.get('email', ''))
    enabled = user_2fa and user_2fa.get('totp_enabled')

    return render_template('twofa_setup.html', secret=secret, qr_code=qr, enabled=enabled, pending=False)


@twofa_bp.route('/2fa/verify', methods=['GET', 'POST'])
def verify():
    if 'pre_2fa_user_id' not in session:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        code = request.form.get('totp_code')
        if not code:
            flash('Please enter the verification code.', 'danger')
            return render_template('twofa_verify.html')

        user_id = session['pre_2fa_user_id']
        user_2fa = _get_user_2fa_secret(user_id)

        if not user_2fa or not user_2fa.get('totp_secret'):
            session.pop('pre_2fa_user_id', None)
            return redirect(url_for('auth.login'))

        totp = pyotp.TOTP(user_2fa['totp_secret'])
        if totp.verify(code, valid_window=1):
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT u.user_id, u.name, u.email, u.role_id, r.role_name
                       FROM users u LEFT JOIN role r ON u.role_id = r.role_id
                       WHERE u.user_id = %s""",
                    (user_id,)
                )
                user = cursor.fetchone()
            conn.close()

            session.pop('pre_2fa_user_id', None)
            session['user_id'] = user['user_id']
            session['role_id'] = user['role_id']
            session['name'] = user['name'] or 'User'
            session['role_name'] = user['role_name'] or 'Employee'
            session.permanent = True
            return redirect(url_for('dashboard.dashboard'))
        else:
            flash('Invalid verification code. Please try again.', 'danger')

    return render_template('twofa_verify.html')


def _generate_qr(secret, name, email):
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=name, issuer_name='Nexus ERP')
    img = qrcode.make(uri, box_size=6, border=2)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode()
