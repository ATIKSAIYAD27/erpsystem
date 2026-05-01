from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import pymysql
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint('auth', __name__)

from app.db import get_db_connection

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Please enter both email and password.', 'danger')
            return render_template('login.html')

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                sql = """
                    SELECT u.user_id, u.name, u.email, u.password_hash, u.role_id, r.role_name 
                    FROM users u
                    LEFT JOIN role r ON u.role_id = r.role_id
                    WHERE u.email = %s
                """
                cursor.execute(sql, (email,))
                user = cursor.fetchone()
                
            conn.close()

            if user and check_password_hash(user['password_hash'], password):
                session['user_id'] = user['user_id']
                session['role_id'] = user['role_id']
                session['name'] = user['name'] or 'User'
                session['role_name'] = user['role_name'] or 'Employee'
                return redirect(url_for('dashboard.dashboard')) 
            else:
                flash('Invalid email or password.', 'danger')
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            flash(f'Database error occurred: {str(e)}', 'danger')
            
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role_id = request.form.get('role_id')

        if not all([name, email, password, role_id]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('auth.register'))

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # Check if user already exists
                cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
                if cursor.fetchone():
                    flash('Email already registered.', 'warning')
                    return redirect(url_for('auth.register'))

                # Insert new user
                hashed_pw = generate_password_hash(password)
                cursor.execute(
                    "INSERT INTO users (name, email, password_hash, role_id) VALUES (%s, %s, %s, %s)",
                    (name, email, hashed_pw, role_id)
                )
            conn.commit()
            conn.close()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            flash(f'Database error: {str(e)}', 'danger')

    # For GET request, fetch roles
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT role_id, role_name FROM role")
            roles = cursor.fetchall()
        conn.close()
    except Exception as e:
        roles = []
        
    return render_template('register.html', roles=roles)

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
