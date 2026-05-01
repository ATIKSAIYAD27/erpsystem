from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import pymysql
from werkzeug.security import generate_password_hash
from app.db import get_db_connection

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/settings')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
        conn.close()
        return render_template('profile.html', user=user)
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('dashboard.index'))

@profile_bp.route('/settings/update', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    name = request.form.get('name')
    email = request.form.get('email')
    new_password = request.form.get('new_password')
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if new_password:
                hashed_password = generate_password_hash(new_password)
                cursor.execute("UPDATE users SET name=%s, email=%s, password=%s WHERE user_id=%s", (name, email, hashed_password, user_id))
            else:
                cursor.execute("UPDATE users SET name=%s, email=%s WHERE user_id=%s", (name, email, user_id))
        conn.commit()
        conn.close()
        session['name'] = name # Update session
        flash('Profile updated successfully!', 'success')
    except Exception as e:
        flash(f'Update failed: {str(e)}', 'danger')
        
    return redirect(url_for('profile.index'))
