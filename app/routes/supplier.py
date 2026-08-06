from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import pymysql
from app.utils import login_required, admin_required

supplier_bp = Blueprint('supplier', __name__)

from app.db import get_db_connection


@supplier_bp.route('/suppliers')
@login_required
def supplier_list():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

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
        flash(f'Database error: {str(e)}', 'danger')
        return render_template('suppliers.html', suppliers=[])


@supplier_bp.route('/suppliers/add', methods=['POST'])
@login_required
def add_supplier():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

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

    except pymysql.err.IntegrityError:
        flash('A supplier with this email already exists.', 'danger')
    except Exception as e:
        flash(f'Error adding supplier: {str(e)}', 'danger')

    return redirect(url_for('supplier.supplier_list'))


@supplier_bp.route('/suppliers/edit/<int:supplier_id>', methods=['POST'])
@login_required
def edit_supplier(supplier_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

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
        flash(f'Error updating supplier: {str(e)}', 'danger')

    return redirect(url_for('supplier.supplier_list'))


@supplier_bp.route('/suppliers/delete/<int:supplier_id>')
@login_required
@admin_required
def delete_supplier(supplier_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

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
        flash(f'Error deleting supplier: {str(e)}', 'danger')

    return redirect(url_for('supplier.supplier_list'))
