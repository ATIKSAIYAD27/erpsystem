from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import pymysql
from app.db import get_db_connection

leave_bp = Blueprint('leave', __name__)

@leave_bp.route('/leaves')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Check if user is an employee
            cursor.execute("SELECT emp_id FROM employee WHERE user_id = %s", (user_id,))
            emp = cursor.fetchone()
            
            # Fetch all leaves for admin/manager view
            cursor.execute("""
                SELECT l.*, u.name as emp_name, e.job_title 
                FROM leaves l
                JOIN employee e ON l.emp_id = e.emp_id
                JOIN users u ON e.user_id = u.user_id
                ORDER BY l.created_at DESC
            """)
            all_leaves = cursor.fetchall()
            
            my_leaves = []
            if emp:
                cursor.execute("SELECT * FROM leaves WHERE emp_id = %s ORDER BY created_at DESC", (emp['emp_id'],))
                my_leaves = cursor.fetchall()
                
        conn.close()
        return render_template('leave.html', all_leaves=all_leaves, my_leaves=my_leaves, is_employee=bool(emp))
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('dashboard.index'))

@leave_bp.route('/leave/apply', methods=['POST'])
def apply_leave():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    leave_type = request.form.get('leave_type')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    reason = request.form.get('reason')
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT emp_id FROM employee WHERE user_id = %s", (user_id,))
            emp = cursor.fetchone()
            if not emp:
                flash('Only employees can apply for leaves.', 'warning')
                return redirect(url_for('leave.index'))
                
            cursor.execute("""
                INSERT INTO leaves (emp_id, leave_type, start_date, end_date, reason)
                VALUES (%s, %s, %s, %s, %s)
            """, (emp['emp_id'], leave_type, start_date, end_date, reason))
        conn.commit()
        conn.close()
        flash('Leave request submitted successfully!', 'success')
    except Exception as e:
        flash(f'Submission failed: {str(e)}', 'danger')
        
    return redirect(url_for('leave.index'))

@leave_bp.route('/leave/action/<int:leave_id>/<string:status>')
def leave_action(leave_id, status):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    # In a real system, we'd check for admin/manager role here
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("UPDATE leaves SET status = %s WHERE leave_id = %s", (status, leave_id))
        conn.commit()
        conn.close()
        flash(f'Leave {status} successfully.', 'success')
    except Exception as e:
        flash(f'Action failed: {str(e)}', 'danger')
        
    return redirect(url_for('leave.index'))
