from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.utils import login_required, manager_or_admin_required, admin_required
import logging

customer_bp = Blueprint('customer', __name__)

logger = logging.getLogger(__name__)

from app.db import get_db_connection


@customer_bp.route('/customers')
@login_required
def customer_list():
    search_query = request.args.get('q', '')
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if search_query:
                sql = """
                    SELECT c.customer_id, c.name, c.email, c.phone, c.address,
                           COUNT(s.sale_id) as sale_count
                    FROM customer c
                    LEFT JOIN sale s ON c.customer_id = s.customer_id
                    WHERE c.name LIKE %s OR c.email LIKE %s OR c.phone LIKE %s
                    GROUP BY c.customer_id, c.name, c.email, c.phone, c.address
                    ORDER BY c.customer_id DESC
                """
                cursor.execute(sql, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
            else:
                sql = """
                    SELECT c.customer_id, c.name, c.email, c.phone, c.address,
                           COUNT(s.sale_id) as sale_count
                    FROM customer c
                    LEFT JOIN sale s ON c.customer_id = s.customer_id
                    GROUP BY c.customer_id, c.name, c.email, c.phone, c.address
                    ORDER BY c.customer_id DESC
                """
                cursor.execute(sql)
            customers = cursor.fetchall()

        conn.close()
        return render_template('customers.html', customers=customers)

    except Exception as e:
        logger.error("Customer list error: %s", e)
        flash('An unexpected error occurred.', 'danger')
        return render_template('customers.html', customers=[])


@customer_bp.route('/customers/add', methods=['POST'])
@manager_or_admin_required
def add_customer():
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    address = request.form.get('address')

    if not all([name, email, phone, address]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('customer.customer_list'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO customer (name, email, phone, address)
                VALUES (%s, %s, %s, %s)
            """, (name, email, phone, address))
        conn.commit()
        conn.close()
        flash('Customer added successfully.', 'success')

    except Exception as e:
        logger.error("Add customer error: %s", e)
        flash('A customer with this email may already exist.', 'danger')

    return redirect(url_for('customer.customer_list'))


@customer_bp.route('/customers/edit/<int:customer_id>', methods=['POST'])
@manager_or_admin_required
def edit_customer(customer_id):
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    address = request.form.get('address')

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE customer
                SET name=%s, email=%s, phone=%s, address=%s
                WHERE customer_id=%s
            """, (name, email, phone, address, customer_id))
        conn.commit()
        conn.close()
        flash('Customer updated successfully.', 'success')
    except Exception as e:
        logger.error("Edit customer error: %s", e)
        flash('An unexpected error occurred.', 'danger')

    return redirect(url_for('customer.customer_list'))


@customer_bp.route('/customers/delete/<int:customer_id>', methods=['POST'])
@admin_required
def delete_customer(customer_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM sale WHERE customer_id = %s", (customer_id,))
            if cursor.fetchone()['count'] > 0:
                flash('Cannot delete customer as they have sale records associated with them.', 'warning')
                return redirect(url_for('customer.customer_list'))

            cursor.execute("DELETE FROM customer WHERE customer_id = %s", (customer_id,))
        conn.commit()
        conn.close()
        from app.utils import log_audit
        log_audit(session['user_id'], f"Deleted customer {customer_id}")
        flash('Customer deleted successfully.', 'success')
    except Exception as e:
        logger.error("Delete customer error: %s", e)
        flash('An unexpected error occurred.', 'danger')

    return redirect(url_for('customer.customer_list'))
