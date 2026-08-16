from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.utils import login_required, manager_or_admin_required, admin_required
import logging

supplier_bp = Blueprint('supplier', __name__)

logger = logging.getLogger(__name__)

from app.db import get_db_connection


@supplier_bp.route('/suppliers')
@login_required
def supplier_list():
    search_query = request.args.get('q', '')
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if search_query:
                sql = """
                    SELECT supplier_id, name, email, phone, address
                    FROM supplier
                    WHERE name LIKE %s OR email LIKE %s OR phone LIKE %s
                    ORDER BY supplier_id DESC
                """
                cursor.execute(sql, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
            else:
                sql = """
                    SELECT supplier_id, name, email, phone, address
                    FROM supplier
                    ORDER BY supplier_id DESC
                """
                cursor.execute(sql)
            suppliers = cursor.fetchall()

        conn.close()
        return render_template('suppliers.html', suppliers=suppliers)

    except Exception as e:
        logger.error("Supplier list error: %s", e)
        flash('An unexpected error occurred.', 'danger')
        return render_template('suppliers.html', suppliers=[])


@supplier_bp.route('/suppliers/add', methods=['POST'])
@manager_or_admin_required
def add_supplier():
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    address = request.form.get('address')

    if not all([name, email, phone, address]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('supplier.supplier_list'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO supplier (name, email, phone, address)
                VALUES (%s, %s, %s, %s)
            """, (name, email, phone, address))
        conn.commit()
        conn.close()
        flash('Supplier added successfully.', 'success')

    except Exception as e:
        logger.error("Add supplier error: %s", e)
        flash('A supplier with this email may already exist.', 'danger')

    return redirect(url_for('supplier.supplier_list'))


@supplier_bp.route('/suppliers/edit/<int:supplier_id>', methods=['POST'])
@manager_or_admin_required
def edit_supplier(supplier_id):
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    address = request.form.get('address')

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE supplier
                SET name=%s, email=%s, phone=%s, address=%s
                WHERE supplier_id=%s
            """, (name, email, phone, address, supplier_id))
        conn.commit()
        conn.close()
        flash('Supplier updated successfully.', 'success')
    except Exception as e:
        logger.error("Edit supplier error: %s", e)
        flash('An unexpected error occurred.', 'danger')

    return redirect(url_for('supplier.supplier_list'))


@supplier_bp.route('/suppliers/delete/<int:supplier_id>', methods=['POST'])
@admin_required
def delete_supplier(supplier_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM purchase_order WHERE supplier_id = %s", (supplier_id,))
            if cursor.fetchone()['count'] > 0:
                flash('Cannot delete supplier as they have purchase orders associated with them.', 'warning')
                return redirect(url_for('supplier.supplier_list'))

            cursor.execute("DELETE FROM supplier WHERE supplier_id = %s", (supplier_id,))
        conn.commit()
        conn.close()
        flash('Supplier deleted successfully.', 'success')
    except Exception as e:
        logger.error("Delete supplier error: %s", e)
        flash('An unexpected error occurred.', 'danger')

    return redirect(url_for('supplier.supplier_list'))
