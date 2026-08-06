from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import pymysql
from app.db import get_db_connection
from app.utils import login_required, admin_required, log_audit

leave_bp = Blueprint('leave', __name__)

@leave_bp.route('/leaves')
@login_required
def index():
    user_id = session['user_id']
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT emp_id FROM employee WHERE user_id = %s", (user_id,))
            emp = cursor.fetchone()

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

            leave_balances = []
            if emp:
                cursor.execute("SELECT * FROM leave_balance WHERE emp_id = %s", (emp['emp_id'],))
                leave_balances = cursor.fetchall()
                
        conn.close()
        return render_template('leave.html', all_leaves=all_leaves, my_leaves=my_leaves, is_employee=bool(emp), leave_balances=leave_balances)
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('dashboard.dashboard'))

@leave_bp.route('/leave/apply', methods=['POST'])
@login_required
def apply_leave():
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

            from datetime import datetime
            sd = datetime.strptime(start_date, '%Y-%m-%d').date()
            ed = datetime.strptime(end_date, '%Y-%m-%d').date()
            days_requested = (ed - sd).days + 1

            if days_requested <= 0:
                flash('End date must be on or after start date.', 'danger')
                return redirect(url_for('leave.index'))

            cursor.execute("""
                SELECT balance_id, total_days, used_days 
                FROM leave_balance 
                WHERE emp_id = %s AND leave_type = %s
            """, (emp['emp_id'], leave_type))
            balance = cursor.fetchone()

            if not balance:
                flash(f'No leave balance found for {leave_type}. Contact HR.', 'danger')
                return redirect(url_for('leave.index'))

            remaining = balance['total_days'] - balance['used_days']
            if days_requested > remaining:
                flash(f'Insufficient {leave_type} leave balance. Remaining: {remaining} days, Requested: {days_requested} days.', 'danger')
                return redirect(url_for('leave.index'))
                
            cursor.execute("""
                INSERT INTO leaves (emp_id, leave_type, start_date, end_date, reason)
                VALUES (%s, %s, %s, %s, %s)
            """, (emp['emp_id'], leave_type, start_date, end_date, reason))
            
            from app.utils import notify_admin
            notify_admin(f"New leave request from employee ID {emp['emp_id']} ({leave_type})", 'warning')

        conn.commit()
        conn.close()
        log_audit(user_id, f"Applied for {leave_type} leave: {start_date} to {end_date}")
        flash('Leave request submitted successfully!', 'success')
    except Exception as e:
        flash(f'Submission failed: {str(e)}', 'danger')
        
    return redirect(url_for('leave.index'))

@leave_bp.route('/leave/action/<int:leave_id>/<string:status>')
@admin_required
def leave_action(leave_id, status):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT e.user_id, l.leave_type, l.start_date, l.end_date
                FROM leaves l 
                JOIN employee e ON l.emp_id = e.emp_id 
                WHERE l.leave_id = %s
            """, (leave_id,))
            leave_info = cursor.fetchone()

            if not leave_info:
                flash('Leave request not found.', 'danger')
                return redirect(url_for('leave.index'))

            cursor.execute("UPDATE leaves SET status = %s WHERE leave_id = %s", (status, leave_id))

            if status == 'Approved':
                from datetime import datetime
                sd = datetime.strptime(str(leave_info['start_date']), '%Y-%m-%d').date()
                ed = datetime.strptime(str(leave_info['end_date']), '%Y-%m-%d').date()
                days = (ed - sd).days + 1

                cursor.execute("""
                    UPDATE leave_balance 
                    SET used_days = used_days + %s 
                    WHERE emp_id = (SELECT emp_id FROM leaves WHERE leave_id = %s) 
                    AND leave_type = %s
                """, (days, leave_id, leave_info['leave_type']))
            
            if leave_info:
                from app.utils import create_notification
                create_notification(leave_info['user_id'], f"Your {leave_info['leave_type']} leave has been {status}.", 'info' if status == 'Approved' else 'danger')

        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Leave {leave_id} {status}")
        flash(f'Leave {status} successfully.', 'success')
    except Exception as e:
        flash(f'Action failed: {str(e)}', 'danger')
        
    return redirect(url_for('leave.index'))

@leave_bp.route('/leave/cancel/<int:leave_id>', methods=['POST'])
@login_required
def cancel_leave(leave_id):
    user_id = session['user_id']

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT l.emp_id, l.status, e.user_id 
                FROM leaves l
                JOIN employee e ON l.emp_id = e.emp_id
                WHERE l.leave_id = %s
            """, (leave_id,))
            leave = cursor.fetchone()

            if not leave:
                flash('Leave request not found.', 'danger')
                return redirect(url_for('leave.index'))

            if leave['user_id'] != user_id:
                flash('You can only cancel your own leave requests.', 'danger')
                return redirect(url_for('leave.index'))

            if leave['status'] != 'Pending':
                flash('Only pending leave requests can be cancelled.', 'warning')
                return redirect(url_for('leave.index'))

            cursor.execute("DELETE FROM leaves WHERE leave_id = %s", (leave_id,))

        conn.commit()
        conn.close()
        log_audit(user_id, f"Cancelled leave request {leave_id}")
        flash('Leave request cancelled successfully.', 'success')
    except Exception as e:
        flash(f'Error cancelling leave: {str(e)}', 'danger')

    return redirect(url_for('leave.index'))
