from flask import Blueprint, request, redirect, url_for, session, flash, send_file, jsonify, render_template
from werkzeug.utils import secure_filename
import csv
import io
import os
from datetime import datetime
from app.db import get_db_connection
from app.utils import login_required, admin_required, log_audit, create_notification
import logging

data_io_bp = Blueprint('data_io', __name__)
logger = logging.getLogger(__name__)


def _parse_csv(file_content):
    reader = csv.DictReader(io.StringIO(file_content))
    return list(reader)


@data_io_bp.route('/import-export')
@login_required
@admin_required
def import_export_page():
    return render_template('import_export.html')


@data_io_bp.route('/import/employees', methods=['POST'])
@login_required
@admin_required
def import_employees():
    if 'file' not in request.files:
        flash('No file uploaded.', 'danger')
        return redirect(url_for('data_io.import_export_page'))

    file = request.files['file']
    if not file.filename.endswith('.csv'):
        flash('Please upload a CSV file.', 'danger')
        return redirect(url_for('data_io.import_export_page'))

    try:
        content = file.read().decode('utf-8')
        rows = _parse_csv(content)

        conn = get_db_connection()
        imported = 0
        errors = []
        with conn.cursor() as cursor:
            for i, row in enumerate(rows):
                try:
                    name = row.get('name', '').strip()
                    email = row.get('email', '').strip()
                    department = row.get('department', '').strip()
                    job_title = row.get('job_title', '').strip()
                    salary = float(row.get('salary', 0))
                    phone = row.get('phone', '').strip()

                    if not name or not email:
                        errors.append(f"Row {i+1}: Missing name or email")
                        continue

                    cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
                    if cursor.fetchone():
                        errors.append(f"Row {i+1}: Email {email} already exists")
                        continue

                    from werkzeug.security import generate_password_hash
                    pw = generate_password_hash('Temp@123')
                    cursor.execute(
                        "INSERT INTO users (name, email, password_hash, role_id) VALUES (%s, %s, %s, 3)",
                        (name, email, pw)
                    )
                    user_id = cursor.lastrowid

                    cursor.execute(
                        "INSERT INTO employee (user_id, department, job_title, salary, phone, hire_date) VALUES (%s, %s, %s, %s, %s, CURDATE())",
                        (user_id, department, job_title, salary, phone)
                    )
                    imported += 1
                except Exception as e:
                    errors.append(f"Row {i+1}: {str(e)}")

        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Imported {imported} employees from CSV")
        flash(f'Imported {imported} employees. {len(errors)} errors.', 'success' if imported > 0 else 'warning')
    except Exception as e:
        logger.error("Import employees error: %s", e)
        flash('Import failed.', 'danger')

    return redirect(url_for('data_io.import_export_page'))


@data_io_bp.route('/import/products', methods=['POST'])
@login_required
@admin_required
def import_products():
    if 'file' not in request.files:
        flash('No file uploaded.', 'danger')
        return redirect(url_for('data_io.import_export_page'))

    file = request.files['file']
    if not file.filename.endswith('.csv'):
        flash('Please upload a CSV file.', 'danger')
        return redirect(url_for('data_io.import_export_page'))

    try:
        content = file.read().decode('utf-8')
        rows = _parse_csv(content)

        conn = get_db_connection()
        imported = 0
        with conn.cursor() as cursor:
            for row in rows:
                name = row.get('name', '').strip()
                sku = row.get('sku', '').strip()
                if not name:
                    continue
                cursor.execute("""
                    INSERT INTO product (name, sku, description, unit_price, quantity, reorder_level)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (name, sku, row.get('description', ''), float(row.get('unit_price', 0)),
                      int(row.get('quantity', 0)), int(row.get('reorder_level', 10))))
                imported += 1
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Imported {imported} products from CSV")
        flash(f'Imported {imported} products.', 'success')
    except Exception as e:
        logger.error("Import products error: %s", e)
        flash('Import failed.', 'danger')

    return redirect(url_for('data_io.import_export_page'))


@data_io_bp.route('/import/customers', methods=['POST'])
@login_required
@admin_required
def import_customers():
    if 'file' not in request.files:
        flash('No file uploaded.', 'danger')
        return redirect(url_for('data_io.import_export_page'))

    file = request.files['file']
    if not file.filename.endswith('.csv'):
        flash('Please upload a CSV file.', 'danger')
        return redirect(url_for('data_io.import_export_page'))

    try:
        content = file.read().decode('utf-8')
        rows = _parse_csv(content)

        conn = get_db_connection()
        imported = 0
        with conn.cursor() as cursor:
            for row in rows:
                name = row.get('name', '').strip()
                if not name:
                    continue
                cursor.execute("""
                    INSERT INTO customer (name, email, phone, address)
                    VALUES (%s, %s, %s, %s)
                """, (name, row.get('email', ''), row.get('phone', ''), row.get('address', '')))
                imported += 1
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Imported {imported} customers from CSV")
        flash(f'Imported {imported} customers.', 'success')
    except Exception as e:
        logger.error("Import customers error: %s", e)
        flash('Import failed.', 'danger')

    return redirect(url_for('data_io.import_export_page'))


@data_io_bp.route('/export/employees')
@login_required
@admin_required
def export_employees():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT u.name, u.email, e.department, e.job_title, e.salary, e.phone, e.hire_date
                FROM employee e JOIN users u ON e.user_id = u.user_id
                ORDER BY u.name
            """)
            rows = cursor.fetchall()
        conn.close()

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['name', 'email', 'department', 'job_title', 'salary', 'phone', 'hire_date'])
        writer.writeheader()
        for row in rows:
            writer.writerow({k: str(v) if v else '' for k, v in row.items()})

        buffer = io.BytesIO(output.getvalue().encode('utf-8'))
        log_audit(session['user_id'], "Exported employees CSV")
        return send_file(buffer, as_attachment=True, download_name='employees_export.csv', mimetype='text/csv')
    except Exception as e:
        logger.error("Export employees error: %s", e)
        flash('Export failed.', 'danger')
        return redirect(url_for('data_io.import_export_page'))


@data_io_bp.route('/export/products')
@login_required
@admin_required
def export_products():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT name, sku, description, unit_price, quantity, reorder_level FROM product ORDER BY name")
            rows = cursor.fetchall()
        conn.close()

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['name', 'sku', 'description', 'unit_price', 'quantity', 'reorder_level'])
        writer.writeheader()
        for row in rows:
            writer.writerow({k: str(v) if v else '' for k, v in row.items()})

        buffer = io.BytesIO(output.getvalue().encode('utf-8'))
        log_audit(session['user_id'], "Exported products CSV")
        return send_file(buffer, as_attachment=True, download_name='products_export.csv', mimetype='text/csv')
    except Exception as e:
        logger.error("Export products error: %s", e)
        flash('Export failed.', 'danger')
        return redirect(url_for('data_io.import_export_page'))


@data_io_bp.route('/export/customers')
@login_required
@admin_required
def export_customers():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT name, email, phone, address FROM customer ORDER BY name")
            rows = cursor.fetchall()
        conn.close()

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['name', 'email', 'phone', 'address'])
        writer.writeheader()
        for row in rows:
            writer.writerow({k: str(v) if v else '' for k, v in row.items()})

        buffer = io.BytesIO(output.getvalue().encode('utf-8'))
        log_audit(session['user_id'], "Exported customers CSV")
        return send_file(buffer, as_attachment=True, download_name='customers_export.csv', mimetype='text/csv')
    except Exception as e:
        logger.error("Export customers error: %s", e)
        flash('Export failed.', 'danger')
        return redirect(url_for('data_io.import_export_page'))


@data_io_bp.route('/export/sales')
@login_required
@admin_required
def export_sales():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT s.sale_id, c.name as customer, p.name as product, s.quantity,
                       s.total_amount, s.sale_date
                FROM sale s
                LEFT JOIN customer c ON s.customer_id = c.customer_id
                LEFT JOIN product p ON s.product_id = p.product_id
                ORDER BY s.sale_date DESC
            """)
            rows = cursor.fetchall()
        conn.close()

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['sale_id', 'customer', 'product', 'quantity', 'total_amount', 'sale_date'])
        writer.writeheader()
        for row in rows:
            writer.writerow({k: str(v) if v else '' for k, v in row.items()})

        buffer = io.BytesIO(output.getvalue().encode('utf-8'))
        log_audit(session['user_id'], "Exported sales CSV")
        return send_file(buffer, as_attachment=True, download_name='sales_export.csv', mimetype='text/csv')
    except Exception as e:
        logger.error("Export sales error: %s", e)
        flash('Export failed.', 'danger')
        return redirect(url_for('data_io.import_export_page'))
