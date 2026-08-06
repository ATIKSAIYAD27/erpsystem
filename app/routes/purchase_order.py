from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import pymysql
from app.utils import login_required, admin_required

po_bp = Blueprint('po', __name__)

from app.db import get_db_connection


@po_bp.route('/purchase-orders')
@login_required
def po_list():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    status_filter = request.args.get('status', '')
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if status_filter:
                sql = """
                    SELECT po.po_id, po.order_date, po.expected_delivery, po.total_amount, po.status,
                           s.name as supplier_name
                    FROM purchase_order po
                    LEFT JOIN supplier s ON po.supplier_id = s.supplier_id
                    WHERE po.status = %s
                    ORDER BY po.po_id DESC
                """
                cursor.execute(sql, (status_filter,))
            else:
                sql = """
                    SELECT po.po_id, po.order_date, po.expected_delivery, po.total_amount, po.status,
                           s.name as supplier_name
                    FROM purchase_order po
                    LEFT JOIN supplier s ON po.supplier_id = s.supplier_id
                    ORDER BY po.po_id DESC
                """
                cursor.execute(sql)
            purchase_orders = cursor.fetchall()

            cursor.execute("SELECT supplier_id, name FROM supplier ORDER BY name")
            suppliers = cursor.fetchall()

        conn.close()
        return render_template('purchase_orders.html', purchase_orders=purchase_orders, suppliers=suppliers)

    except Exception as e:
        flash(f'Database error: {str(e)}', 'danger')
        return render_template('purchase_orders.html', purchase_orders=[], suppliers=[])


@po_bp.route('/purchase-orders/add', methods=['POST'])
@login_required
def add_po():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    supplier_id = request.form.get('supplier_id')
    order_date = request.form.get('order_date')
    expected_delivery = request.form.get('expected_delivery')
    product_ids = request.form.getlist('product_id[]')
    quantities = request.form.getlist('quantity[]')
    unit_costs = request.form.getlist('unit_cost[]')

    if not all([supplier_id, order_date]):
        flash('Supplier and order date are required.', 'danger')
        return redirect(url_for('po.po_list'))

    if not product_ids:
        flash('At least one item is required.', 'danger')
        return redirect(url_for('po.po_list'))

    try:
        total_amount = 0
        items = []
        for i in range(len(product_ids)):
            qty = int(quantities[i])
            cost = float(unit_costs[i])
            total_amount += qty * cost
            items.append((product_ids[i], qty, cost))

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO purchase_order (supplier_id, order_date, expected_delivery, total_amount, status)
                VALUES (%s, %s, %s, %s, 'Pending')
            """, (supplier_id, order_date, expected_delivery, total_amount))
            po_id = cursor.lastrowid

            for product_id, qty, unit_cost in items:
                cursor.execute("""
                    INSERT INTO purchase_order_item (po_id, product_id, quantity, unit_cost)
                    VALUES (%s, %s, %s, %s)
                """, (po_id, product_id, qty, unit_cost))

        conn.commit()
        conn.close()
        flash('Purchase order created successfully.', 'success')

    except Exception as e:
        flash(f'Error creating purchase order: {str(e)}', 'danger')

    return redirect(url_for('po.po_list'))


@po_bp.route('/purchase-orders/<int:po_id>')
@login_required
def po_detail(po_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT po.*, s.name as supplier_name, s.email as supplier_email, s.phone as supplier_phone
                FROM purchase_order po
                LEFT JOIN supplier s ON po.supplier_id = s.supplier_id
                WHERE po.po_id = %s
            """, (po_id,))
            po = cursor.fetchone()

            if not po:
                flash('Purchase order not found.', 'danger')
                return redirect(url_for('po.po_list'))

            cursor.execute("""
                SELECT poi.*, p.name as product_name, p.sku
                FROM purchase_order_item poi
                LEFT JOIN product p ON poi.product_id = p.product_id
                WHERE poi.po_id = %s
            """, (po_id,))
            items = cursor.fetchall()

        conn.close()
        return render_template('po_detail.html', po=po, items=items)

    except Exception as e:
        flash(f'Database error: {str(e)}', 'danger')
        return redirect(url_for('po.po_list'))


@po_bp.route('/purchase-orders/<int:po_id>/status', methods=['POST'])
@login_required
@admin_required
def update_po_status(po_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    new_status = request.form.get('status')
    valid_statuses = ['Pending', 'Approved', 'Received', 'Cancelled']

    if new_status not in valid_statuses:
        flash('Invalid status selected.', 'danger')
        return redirect(url_for('po.po_detail', po_id=po_id))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT status FROM purchase_order WHERE po_id = %s", (po_id,))
            po = cursor.fetchone()
            if not po:
                flash('Purchase order not found.', 'danger')
                return redirect(url_for('po.po_list'))

            cursor.execute("UPDATE purchase_order SET status = %s WHERE po_id = %s", (new_status, po_id))

            if new_status == 'Received':
                cursor.execute("SELECT product_id, quantity FROM purchase_order_item WHERE po_id = %s", (po_id,))
                items = cursor.fetchall()
                for item in items:
                    cursor.execute("""
                        UPDATE product SET quantity = quantity + %s WHERE product_id = %s
                    """, (item['quantity'], item['product_id']))

        conn.commit()
        conn.close()
        flash(f'Purchase order status updated to {new_status}.', 'success')

    except Exception as e:
        flash(f'Error updating status: {str(e)}', 'danger')

    return redirect(url_for('po.po_detail', po_id=po_id))


@po_bp.route('/purchase-orders/delete/<int:po_id>')
@login_required
@admin_required
def delete_po(po_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM purchase_order_item WHERE po_id = %s", (po_id,))
            cursor.execute("DELETE FROM purchase_order WHERE po_id = %s", (po_id,))
        conn.commit()
        conn.close()
        flash('Purchase order deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting purchase order: {str(e)}', 'danger')

    return redirect(url_for('po.po_list'))
