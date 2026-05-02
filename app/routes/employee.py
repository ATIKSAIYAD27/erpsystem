from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import pymysql

employee_bp = Blueprint('employee', __name__)

from app.db import get_db_connection

@employee_bp.route('/employee')
def employee_list():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    search_query = request.args.get('q', '')
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if search_query:
                sql = """
                    SELECT e.emp_id as id, u.email, u.user_id as user_id, u.name,
                           e.department, e.salary, e.hire_date
                    FROM employee e
                    JOIN users u ON e.user_id = u.user_id
                    WHERE u.name LIKE %s OR u.email LIKE %s OR e.department LIKE %s
                    ORDER BY e.emp_id DESC
                """
                cursor.execute(sql, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
            else:
                sql = """
                    SELECT e.emp_id as id, u.email, u.user_id as user_id, u.name,
                           e.department, e.salary, e.hire_date
                    FROM employee e
                    JOIN users u ON e.user_id = u.user_id
                    ORDER BY e.emp_id DESC
                """
                cursor.execute(sql)
            employees = cursor.fetchall()

            # Fetch users for the add form dropdown
            cursor.execute("SELECT user_id as id, email FROM users ORDER BY email")
            users = cursor.fetchall()

        conn.close()

        return render_template('employee.html', employees=employees, users=users)

    except Exception as e:
        flash(f'Database error: {str(e)}', 'danger')
        return render_template('employee.html', employees=[], users=[])

@employee_bp.route('/employee/add', methods=['POST'])
def add_employee():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = request.form.get('user_id')
    department = request.form.get('department')
    salary = request.form.get('salary')
    hire_date = request.form.get('hire_date')

    if not all([user_id, department, salary, hire_date]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('employee.employee_list'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO employee (user_id, department, salary, hire_date)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql, (user_id, department, salary, hire_date))
            
            # Notify the new employee
            from app.utils import create_notification
            create_notification(user_id, f"Welcome! You have been added as an employee in the {department} department.", 'success')

        conn.commit()
        conn.close()
        flash('Employee added successfully.', 'success')

    except Exception as e:
        flash(f'Error adding employee: {str(e)}', 'danger')

    return redirect(url_for('employee.employee_list'))
