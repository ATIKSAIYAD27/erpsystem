from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.utils import login_required, admin_required, manager_or_admin_required, log_audit
import logging

employee_bp = Blueprint('employee', __name__)

logger = logging.getLogger(__name__)

from app.db import get_db_connection


@employee_bp.route('/employee')
@manager_or_admin_required
def employee_list():
    search_query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    offset = (page - 1) * per_page

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if search_query:
                cursor.execute("SELECT COUNT(*) as total FROM employee e JOIN users u ON e.user_id = u.user_id WHERE u.name LIKE %s OR u.email LIKE %s OR e.department LIKE %s",
                    (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
                total = cursor.fetchone()['total']

                sql = """
                    SELECT e.emp_id as id, u.email, u.user_id as user_id, u.name,
                           e.department, e.salary, e.hire_date, e.job_title
                    FROM employee e
                    JOIN users u ON e.user_id = u.user_id
                    WHERE u.name LIKE %s OR u.email LIKE %s OR e.department LIKE %s
                    ORDER BY e.emp_id DESC
                    LIMIT %s OFFSET %s
                """
                cursor.execute(sql, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', per_page, offset))
            else:
                cursor.execute("SELECT COUNT(*) as total FROM employee")
                total = cursor.fetchone()['total']

                sql = """
                    SELECT e.emp_id as id, u.email, u.user_id as user_id, u.name,
                           e.department, e.salary, e.hire_date, e.job_title
                    FROM employee e
                    JOIN users u ON e.user_id = u.user_id
                    ORDER BY e.emp_id DESC
                    LIMIT %s OFFSET %s
                """
                cursor.execute(sql, (per_page, offset))
            employees = cursor.fetchall()

            cursor.execute("SELECT user_id as id, email FROM users ORDER BY email")
            users = cursor.fetchall()

        conn.close()

        total_pages = (total + per_page - 1) // per_page

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'employees': employees,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages
            })

        return render_template('employee.html', employees=employees, users=users,
                               page=page, per_page=per_page, total=total, total_pages=total_pages)

    except Exception as e:
        logger.error("Employee list error: %s", e)
        flash('An unexpected error occurred.', 'danger')
        return render_template('employee.html', employees=[], users=[], page=1, per_page=25, total=0, total_pages=0)


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
            new_emp_id = cursor.lastrowid

            import datetime
            leave_types = ['Sick', 'Casual', 'Vacation']
            current_year = datetime.datetime.now().year
            for lt in leave_types:
                cursor.execute("""
                    INSERT IGNORE INTO leave_balance (emp_id, leave_type, total_days, used_days, year)
                    VALUES (%s, %s, 12, 0, %s)
                """, (new_emp_id, lt, current_year))

            from app.utils import create_notification
            create_notification(user_id, f"Welcome! You have been added as an employee in the {department} department.", 'success')

        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Added employee for user {user_id} in {department}")

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Employee added successfully.'})
        flash('Employee added successfully.', 'success')

    except Exception as e:
        logger.error("Add employee error: %s", e)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'An unexpected error occurred.'}), 500
        flash('An unexpected error occurred.', 'danger')

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

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Employee updated successfully.'})
        flash('Employee updated successfully.', 'success')
    except Exception as e:
        logger.error("Edit employee error: %s", e)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'An unexpected error occurred.'}), 500
        flash('An unexpected error occurred.', 'danger')

    return redirect(url_for('employee.employee_list'))


@employee_bp.route('/employee/delete/<int:emp_id>', methods=['POST'])
@admin_required
def delete_employee(emp_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM employee WHERE emp_id = %s", (emp_id,))
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Deleted employee {emp_id}")

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Employee deleted successfully.'})
        flash('Employee record deleted successfully.', 'success')
    except Exception as e:
        logger.error("Delete employee error: %s", e)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'An unexpected error occurred.'}), 500
        flash('An unexpected error occurred.', 'danger')

    return redirect(url_for('employee.employee_list'))


@employee_bp.route('/employee/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_employees():
    """Delete multiple employees at once."""
    data = request.get_json()
    ids = data.get('ids', [])
    if not ids:
        return jsonify({'success': False, 'message': 'No employees selected.'}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            placeholders = ','.join(['%s'] * len(ids))
            cursor.execute(f"DELETE FROM employee WHERE emp_id IN ({placeholders})", ids)
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Bulk deleted {len(ids)} employees")
        return jsonify({'success': True, 'message': f'{len(ids)} employees deleted.'})
    except Exception as e:
        logger.error("Bulk delete employees error: %s", e)
        return jsonify({'success': False, 'message': 'Bulk delete failed.'}), 500
