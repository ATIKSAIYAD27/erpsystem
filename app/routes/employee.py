from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import pymysql
from app.utils import login_required, admin_required, manager_or_admin_required, log_audit

employee_bp = Blueprint('employee', __name__)

from app.db import get_db_connection

@employee_bp.route('/employee')
@manager_or_admin_required
def employee_list():
    search_query = request.args.get('q', '')
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if search_query:
                sql = """
                    SELECT e.emp_id as id, u.email, u.user_id as user_id, u.name,
                           e.department, e.salary, e.hire_date, e.job_title
                    FROM employee e
                    JOIN users u ON e.user_id = u.user_id
                    WHERE u.name LIKE %s OR u.email LIKE %s OR e.department LIKE %s
                    ORDER BY e.emp_id DESC
                """
                cursor.execute(sql, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
            else:
                sql = """
                    SELECT e.emp_id as id, u.email, u.user_id as user_id, u.name,
                           e.department, e.salary, e.hire_date, e.job_title
                    FROM employee e
                    JOIN users u ON e.user_id = u.user_id
                    ORDER BY e.emp_id DESC
                """
                cursor.execute(sql)
            employees = cursor.fetchall()

            cursor.execute("SELECT user_id as id, email FROM users ORDER BY email")
            users = cursor.fetchall()

        conn.close()

        return render_template('employee.html', employees=employees, users=users)

    except Exception as e:
        flash(f'Database error: {str(e)}', 'danger')
        return render_template('employee.html', employees=[], users=[])

@employee_bp.route('/employee/add', methods=['POST'])
@manager_or_admin_required
def add_employee():
    user_id = request.form.get('user_id')
    department = request.form.get('department')
    salary = request.form.get('salary')
    hire_date = request.form.get('hire_date')
    job_title = request.form.get('job_title')

    if not all([user_id, department, salary, hire_date]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('employee.employee_list'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO employee (user_id, department, salary, hire_date, job_title)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (user_id, department, salary, hire_date, job_title))

            from app.utils import create_notification
            create_notification(user_id, f"Welcome! You have been added as an employee in the {department} department.", 'success')

        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Added employee for user {user_id} in {department}")
        flash('Employee added successfully.', 'success')

    except Exception as e:
        flash(f'Error adding employee: {str(e)}', 'danger')

    return redirect(url_for('employee.employee_list'))

@employee_bp.route('/employee/edit/<int:emp_id>', methods=['POST'])
@manager_or_admin_required
def edit_employee(emp_id):
    department = request.form.get('department')
    salary = request.form.get('salary')
    hire_date = request.form.get('hire_date')
    job_title = request.form.get('job_title')

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
                UPDATE employee 
                SET department=%s, salary=%s, hire_date=%s, job_title=%s
                WHERE emp_id=%s
            """
            cursor.execute(sql, (department, salary, hire_date, job_title, emp_id))
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Updated employee {emp_id}")
        flash('Employee updated successfully.', 'success')
    except Exception as e:
        flash(f'Error updating employee: {str(e)}', 'danger')

    return redirect(url_for('employee.employee_list'))

@employee_bp.route('/employee/delete/<int:emp_id>')
@admin_required
def delete_employee(emp_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM employee WHERE emp_id = %s", (emp_id,))
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Deleted employee {emp_id}")
        flash('Employee record deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting employee: {str(e)}', 'danger')

    return redirect(url_for('employee.employee_list'))
