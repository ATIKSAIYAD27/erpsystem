from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import pymysql
from datetime import datetime

hr_bp = Blueprint('hr', __name__)

from app.db import get_db_connection

@hr_bp.route('/attendance')
def attendance_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    today = datetime.now().date()
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Check if current user is an employee
            cursor.execute("SELECT emp_id FROM employee WHERE user_id = %s", (user_id,))
            emp_record = cursor.fetchone()
            emp_id = emp_record['emp_id'] if emp_record else None
            
            # Get current user's attendance for today
            my_attendance = None
            if emp_id:
                cursor.execute("SELECT * FROM attendance WHERE emp_id = %s AND date = %s", (emp_id, today))
                my_attendance = cursor.fetchone()
                
            # Get all attendance records for today (for Admin/Manager view)
            cursor.execute("""
                SELECT a.*, u.name as employee_name, u.email, e.department 
                FROM attendance a
                JOIN employee e ON a.emp_id = e.emp_id
                JOIN users u ON e.user_id = u.user_id
                WHERE a.date = %s
                ORDER BY a.check_in DESC
            """, (today,))
            todays_attendance = cursor.fetchall()
            
            # Fetch pending leave requests
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
def process_attendance():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    action = request.form.get('action') # 'check_in' or 'check_out'
    
    # Extract client IP for anti-proxy auditing (USP Feature)
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    today = datetime.now().date()
    current_time = datetime.now().time()

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Ensure user is an employee
            cursor.execute("SELECT emp_id FROM employee WHERE user_id = %s", (user_id,))
            emp = cursor.fetchone()
            if not emp:
                flash('You are not registered as an employee. Contact HR.', 'warning')
                return redirect(url_for('hr.attendance_dashboard'))
                
            emp_id = emp['emp_id']
            
            # Check existing record
            cursor.execute("SELECT * FROM attendance WHERE emp_id = %s AND date = %s", (emp_id, today))
            record = cursor.fetchone()

            if action == 'check_in':
                if record:
                    flash('You have already checked in today.', 'info')
                else:
                    # Determine Late status (Assuming 09:30:00 is late threshold)
                    is_late = current_time > datetime.strptime('09:30:00', '%H:%M:%S').time()
                    status = 'Late' if is_late else 'Present'
                    
                    cursor.execute("""
                        INSERT INTO attendance (emp_id, date, status, check_in) 
                        VALUES (%s, %s, %s, %s)
                    """, (emp_id, today, status, current_time))
                    
                    # Log audit IP
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

@hr_bp.route('/payroll')
def payroll_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Fetch payroll records for selected month/year
            cursor.execute("""
                SELECT p.*, u.name as employee_name, e.department
                FROM payroll p
                JOIN employee e ON p.emp_id = e.emp_id
                JOIN users u ON e.user_id = u.user_id
                WHERE p.month = %s AND p.year = %s
            """, (month, year))
            payroll_records = cursor.fetchall()
            
            # Fetch total disbursement
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
def generate_payroll():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    month = int(request.form.get('month'))
    year = int(request.form.get('year'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 1. Get all employees
            cursor.execute("SELECT emp_id, salary FROM employee")
            employees = cursor.fetchall()

            for emp in employees:
                # 2. Check if payroll already exists
                cursor.execute("SELECT payroll_id FROM payroll WHERE emp_id = %s AND month = %s AND year = %s", 
                              (emp['emp_id'], month, year))
                if cursor.fetchone():
                    continue # Skip if already generated

                # 3. Simple calculation: Net = Basic (no deductions for now)
                basic = emp['salary']
                deductions = 0
                net_pay = basic - deductions

                cursor.execute("""
                    INSERT INTO payroll (emp_id, month, year, basic, deductions, net_pay)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (emp['emp_id'], month, year, basic, deductions, net_pay))

        conn.commit()
        conn.close()
        flash(f'Payroll generated for {month}/{year} successfully.', 'success')

    except Exception as e:
        flash(f'Error generating payroll: {str(e)}', 'danger')

    return redirect(url_for('hr.payroll_dashboard', month=month, year=year))

