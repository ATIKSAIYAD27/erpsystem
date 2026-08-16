from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.utils import login_required, manager_or_admin_required, admin_required, log_audit, get_db, safe_int, safe_float
import logging

po_bp = Blueprint('po', __name__)

logger = logging.getLogger(__name__)


@po_bp.route('/purchase-orders')
@login_required
def po_list():
    status_filter = request.args.get('status', '')
    try:
        with get_db() as conn:
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

        return render_template('purchase_orders.html', purchase_orders=purchase_orders, suppliers=suppliers)

    except Exception as e:
        logger.error("PO list error: %s", e)
        flash('An unexpected error occurred.', 'danger')
        return render_template('purchase_orders.html', purchase_orders=[], suppliers=[])


@po_bp.route('/purchase-orders/add', methods=['POST'])
@manager_or_admin_required
def add_po():
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
            qty = safe_int(quantities[i], 0)
            cost = safe_float(unit_costs[i], 0)
            if qty <= 0 or cost <= 0:
                flash(f'Invalid quantity or cost for item {i+1}.', 'danger')
                return redirect(url_for('po.po_list'))
            total_amount += qty * cost
            items.append((product_ids[i], qty, cost))

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO purchase_order (supplier_id, order_date, expected_delivery, total_amount, status, created_by)
                    VALUES (%s, %s, %s, %s, 'Pending', %s)
                    RETURNING po_id
                """, (supplier_id, order_date, expected_delivery, total_amount, session['user_id']))
                po_id = cursor.fetchone()['po_id']

                for product_id, qty, unit_cost in items:
                    cursor.execute("""
                        INSERT INTO purchase_order_item (po_id, product_id, quantity, unit_cost)
                        VALUES (%s, %s, %s, %s)
                    """, (po_id, product_id, qty, unit_cost))

            conn.commit()
        log_audit(session['user_id'], f"Created purchase order {po_id}")
        flash('Purchase order created successfully.', 'success')

    except Exception as e:
        logger.error("Add PO error: %s", e)
        flash('An unexpected error occurred.', 'danger')

    return redirect(url_for('po.po_list'))


@po_bp.route('/purchase-orders/<int:po_id>')
@login_required
def po_detail(po_id):
    try:
        with get_db() as conn:
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

        return render_template('po_detail.html', po=po, items=items)

    except Exception as e:
        logger.error("PO detail error: %s", e)
        flash('An unexpected error occurred.', 'danger')
        return redirect(url_for('po.po_list'))


@po_bp.route('/purchase-orders/<int:po_id>/status', methods=['POST'])
@manager_or_admin_required
def update_po_status(po_id):
    new_status = request.form.get('status')
    valid_statuses = ['Pending', 'Approved', 'Received', 'Cancelled']

    if new_status not in valid_statuses:
        flash('Invalid status selected.', 'danger')
        return redirect(url_for('po.po_detail', po_id=po_id))

    try:
        with get_db() as conn:
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
        log_audit(session['user_id'], f"Updated PO {po_id} status to {new_status}")
        flash(f'Purchase order status updated to {new_status}.', 'success')

    except Exception as e:
        logger.error("Update PO status error: %s", e)
        flash('An unexpected error occurred.', 'danger')

    return redirect(url_for('po.po_detail', po_id=po_id))


@po_bp.route('/purchase-orders/delete/<int:po_id>', methods=['POST'])
@admin_required
def delete_po(po_id):
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM purchase_order_item WHERE po_id = %s", (po_id,))
                cursor.execute("DELETE FROM purchase_order WHERE po_id = %s", (po_id,))
            conn.commit()
        log_audit(session['user_id'], f"Deleted purchase order {po_id}")
        flash('Purchase order deleted successfully.', 'success')
    except Exception as e:
        logger.error("Delete PO error: %s", e)
        flash('An unexpected error occurred.', 'danger')

    return redirect(url_for('po.po_list'))
