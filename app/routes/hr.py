from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import pymysql
from datetime import datetime
import pytz
import os

hr_bp = Blueprint('hr', __name__)

def get_current_time():
    tz_name = os.environ.get('TZ', 'Asia/Kolkata')
    tz = pytz.timezone(tz_name)
    return datetime.now(tz)

from app.db import get_db_connection
from app.utils import login_required, admin_required, manager_or_admin_required, log_audit

@hr_bp.route('/attendance')
@login_required
def attendance_dashboard():
    user_id = session['user_id']
    now = get_current_time()
    today = now.date()
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT emp_id FROM employee WHERE user_id = %s", (user_id,))
            emp_record = cursor.fetchone()
            emp_id = emp_record['emp_id'] if emp_record else None
            
            my_attendance = None
            if emp_id:
                cursor.execute("SELECT * FROM attendance WHERE emp_id = %s AND date = %s", (emp_id, today))
                my_attendance = cursor.fetchone()
                
            cursor.execute("""
                SELECT a.*, u.name as employee_name, u.email, e.department 
                FROM attendance a
                JOIN employee e ON a.emp_id = e.emp_id
                JOIN users u ON e.user_id = u.user_id
                WHERE a.date = %s
                ORDER BY a.check_in DESC
            """, (today,))
            todays_attendance = cursor.fetchall()
            
            cursor.execute("""
                SELECT l.*, u.name as employee_name
                FROM leaves l
                JOIN employee e ON l.emp_id = e.emp_id
                JOIN users u ON e.user_id = u.user_id
                WHERE l.status = 'Pending'
            """)
            leave_requests = cursor.fetchall()

        conn.close()

        return render_template('attendance.html', 
                               my_attendance=my_attendance, 
                               todays_attendance=todays_attendance,
                               leave_requests=leave_requests,
                               emp_id=emp_id)

    except Exception as e:
        flash(f'Database error: {str(e)}', 'danger')
        return render_template('attendance.html', my_attendance=None, todays_attendance=[], leave_requests=[], emp_id=None)

@hr_bp.route('/attendance/check', methods=['POST'])
@login_required
def process_attendance():
    user_id = session['user_id']
    action = request.form.get('action')
    
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    now = get_current_time()
    today = now.date()
    current_time = now.time()

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT emp_id FROM employee WHERE user_id = %s", (user_id,))
            emp = cursor.fetchone()
            if not emp:
                flash('You are not registered as an employee. Contact HR.', 'warning')
                return redirect(url_for('hr.attendance_dashboard'))
                
            emp_id = emp['emp_id']
            
            cursor.execute("SELECT * FROM attendance WHERE emp_id = %s AND date = %s", (emp_id, today))
            record = cursor.fetchone()

            if action == 'check_in':
                if record:
                    flash('You have already checked in today.', 'info')
                else:
                    is_late = current_time > datetime.strptime('09:30:00', '%H:%M:%S').time()
                    status = 'Late' if is_late else 'Present'
                    
                    cursor.execute("""
                        INSERT INTO attendance (emp_id, date, status, check_in) 
                        VALUES (%s, %s, %s, %s)
                    """, (emp_id, today, status, current_time))
                    
                    cursor.execute("INSERT INTO audit_log (user_id, action, ip_address) VALUES (%s, %s, %s)", 
                                  (user_id, f"Check-in at {current_time}", client_ip))
                    flash('Checked in successfully.', 'success')

            elif action == 'check_out':
                if not record:
                    flash('You must check in first!', 'danger')
                elif record['check_out']:
                    flash('You have already checked out today.', 'info')
                else:
                    cursor.execute("""
                        UPDATE attendance 
                        SET check_out = %s 
                        WHERE emp_id = %s AND date = %s
                    """, (current_time, emp_id, today))
                    flash('Checked out successfully.', 'success')

        conn.commit()
        conn.close()

    except Exception as e:
        flash(f'Error processing attendance: {str(e)}', 'danger')

    return redirect(url_for('hr.attendance_dashboard'))

@hr_bp.route('/attendance/history')
@login_required
def attendance_history():
    user_id = session['user_id']
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT emp_id FROM employee WHERE user_id = %s", (user_id,))
            emp_record = cursor.fetchone()

            is_privileged = session.get('role_name') in ('Admin', 'Manager')

            if is_privileged:
                base_sql = """
                    SELECT a.*, u.name as employee_name, e.department 
                    FROM attendance a
                    JOIN employee e ON a.emp_id = e.emp_id
                    JOIN users u ON e.user_id = u.user_id
                """
                params = []
                conditions = []

                if start_date:
                    conditions.append("a.date >= %s")
                    params.append(start_date)
                if end_date:
                    conditions.append("a.date <= %s")
                    params.append(end_date)

                if conditions:
                    base_sql += " WHERE " + " AND ".join(conditions)

                base_sql += " ORDER BY a.date DESC, a.check_in DESC"
                cursor.execute(base_sql, tuple(params))
            else:
                if not emp_record:
                    flash('No employee record found.', 'warning')
                    return render_template('attendance_history.html', records=[])

                base_sql = """
                    SELECT a.*, u.name as employee_name, e.department 
                    FROM attendance a
                    JOIN employee e ON a.emp_id = e.emp_id
                    JOIN users u ON e.user_id = u.user_id
                    WHERE a.emp_id = %s
                """
                params = [emp_record['emp_id']]

                if start_date:
                    base_sql += " AND a.date >= %s"
                    params.append(start_date)
                if end_date:
                    base_sql += " AND a.date <= %s"
                    params.append(end_date)

                base_sql += " ORDER BY a.date DESC, a.check_in DESC"
                cursor.execute(base_sql, tuple(params))

            records = cursor.fetchall()

        conn.close()
        return render_template('attendance_history.html', records=records, start_date=start_date, end_date=end_date)

    except Exception as e:
        flash(f'Database error: {str(e)}', 'danger')
        return render_template('attendance_history.html', records=[], start_date=start_date, end_date=end_date)

@hr_bp.route('/payroll')
@manager_or_admin_required
def payroll_dashboard():
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT p.*, u.name as employee_name, e.department
                FROM payroll p
                JOIN employee e ON p.emp_id = e.emp_id
                JOIN users u ON e.user_id = u.user_id
                WHERE p.month = %s AND p.year = %s
            """, (month, year))
            payroll_records = cursor.fetchall()
            
            cursor.execute("SELECT SUM(net_pay) as total FROM payroll WHERE month = %s AND year = %s", (month, year))
            total_disbursement = cursor.fetchone()['total'] or 0

        conn.close()

        return render_template('payroll.html', 
                               payroll=payroll_records, 
                               month=month, 
                               year=year,
                               total_disbursement=total_disbursement)

    except Exception as e:
        flash(f'Database error: {str(e)}', 'danger')
        return render_template('payroll.html', payroll=[], month=month, year=year, total_disbursement=0)

@hr_bp.route('/payroll/generate', methods=['POST'])
@manager_or_admin_required
def generate_payroll():
    month = int(request.form.get('month', datetime.now().month))
    year = int(request.form.get('year', datetime.now().year))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT emp_id, salary FROM employee")
            employees = cursor.fetchall()

            for emp in employees:
                cursor.execute("SELECT payroll_id FROM payroll WHERE emp_id = %s AND month = %s AND year = %s", 
                              (emp['emp_id'], month, year))
                if cursor.fetchone():
                    continue

                basic = emp['salary']
                deductions = 0
                net_pay = basic - deductions

                cursor.execute("""
                    INSERT INTO payroll (emp_id, month, year, basic, deductions, net_pay)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (emp['emp_id'], month, year, basic, deductions, net_pay))

        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Generated payroll for {month}/{year}")
        flash(f'Payroll generated for {month}/{year} successfully.', 'success')

    except Exception as e:
        flash(f'Error generating payroll: {str(e)}', 'danger')

    return redirect(url_for('hr.payroll_dashboard', month=month, year=year))
