from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime
from app.utils import login_required, admin_required, manager_or_admin_required, log_audit
import logging

sales_bp = Blueprint('sales', __name__)

logger = logging.getLogger(__name__)

from app.db import get_db_connection


@sales_bp.route('/sales')
@manager_or_admin_required
def sales_dashboard():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    offset = (page - 1) * per_page

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as total FROM sale")
            total = cursor.fetchone()['total']

            sql = """
                SELECT s.sale_id, s.quantity, s.total_amount, s.sale_date,
                       c.name as customer_name, p.name as product_name
                FROM sale s
                LEFT JOIN customer c ON s.customer_id = c.customer_id
                LEFT JOIN product p ON s.product_id = p.product_id
                ORDER BY s.sale_date DESC, s.sale_id DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(sql, (per_page, offset))
            recent_sales = cursor.fetchall()

            cursor.execute("SELECT customer_id, name FROM customer ORDER BY name")
            customers = cursor.fetchall()

            cursor.execute("SELECT product_id, name, unit_price, quantity as stock_left FROM product WHERE quantity > 0")
            products = cursor.fetchall()

            cursor.execute("SELECT SUM(total_amount) as total FROM sale")
            total_revenue = cursor.fetchone()['total'] or 0

        conn.close()

        total_pages = (total + per_page - 1) // per_page

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'sales': recent_sales,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages,
                'total_revenue': total_revenue
            })

        return render_template('sales.html', sales=recent_sales,
                               customers=customers, products=products,
                               total_revenue=total_revenue,
                               page=page, per_page=per_page, total=total, total_pages=total_pages)

    except Exception as e:
        logger.error("Sales dashboard error: %s", e)
        flash('An unexpected error occurred.', 'danger')
        return render_template('sales.html', sales=[], customers=[], products=[], total_revenue=0,
                               page=1, per_page=25, total=0, total_pages=0)


@sales_bp.route('/sales/add', methods=['POST'])
@manager_or_admin_required
def add_sale():
    customer_id = request.form.get('customer_id')
    product_id = request.form.get('product_id')
    quantity = int(request.form.get('quantity', 0))
    sale_date = request.form.get('sale_date') or datetime.now().strftime('%Y-%m-%d')

    if not all([customer_id, product_id, quantity]):
        flash('All required fields must be filled.', 'danger')
        return redirect(url_for('sales.sales_dashboard'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT unit_price, quantity FROM product WHERE product_id = %s", (product_id,))
            product = cursor.fetchone()

            if not product:
                flash('Invalid product selected.', 'danger')
                return redirect(url_for('sales.sales_dashboard'))

            if product['quantity'] < quantity:
                flash(f'Insufficient stock! Only {product["quantity"]} units available.', 'warning')
                return redirect(url_for('sales.sales_dashboard'))

            total_amount = float(product['unit_price']) * quantity

            cursor.execute("""
                INSERT INTO sale (customer_id, product_id, quantity, total_amount, sale_date)
                VALUES (%s, %s, %s, %s, %s)
            """, (customer_id, product_id, quantity, total_amount, sale_date))

            cursor.execute("""
                UPDATE product SET quantity = quantity - %s WHERE product_id = %s
            """, (quantity, product_id))

            from app.utils import notify_admin
            notify_admin(f"New Sale: {quantity} units of product ID {product_id} sold for Rs.{total_amount:,.2f}", 'success')

        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Recorded sale: {quantity} units of product {product_id} for Rs.{total_amount:,.2f}")

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Sale recorded successfully!'})
        flash('Sale recorded successfully! Inventory updated.', 'success')

    except Exception as e:
        logger.error("Add sale error: %s", e)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'An unexpected error occurred.'}), 500
        flash('An unexpected error occurred.', 'danger')

    return redirect(url_for('sales.sales_dashboard'))


@sales_bp.route('/sales/edit/<int:sale_id>', methods=['POST'])
@manager_or_admin_required
def edit_sale(sale_id):
    new_quantity = int(request.form.get('quantity', 0))

    if new_quantity <= 0:
        flash('Quantity must be greater than zero.', 'danger')
        return redirect(url_for('sales.sales_dashboard'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT product_id, quantity, total_amount FROM sale WHERE sale_id = %s", (sale_id,))
            old_sale = cursor.fetchone()

            if not old_sale:
                flash('Sale record not found.', 'danger')
                return redirect(url_for('sales.sales_dashboard'))

            cursor.execute("SELECT unit_price, quantity FROM product WHERE product_id = %s", (old_sale['product_id'],))
            product = cursor.fetchone()

            if not product:
                flash('Product not found.', 'danger')
                return redirect(url_for('sales.sales_dashboard'))

            old_qty = old_sale['quantity']
            qty_diff = new_quantity - old_qty

            if product['quantity'] < qty_diff:
                flash(f'Insufficient stock! Only {product["quantity"]} additional units available.', 'warning')
                return redirect(url_for('sales.sales_dashboard'))

            new_total = float(product['unit_price']) * new_quantity

            cursor.execute("UPDATE sale SET quantity = %s, total_amount = %s WHERE sale_id = %s",
                           (new_quantity, new_total, sale_id))
            cursor.execute("UPDATE product SET quantity = quantity - %s WHERE product_id = %s",
                           (qty_diff, old_sale['product_id']))

        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Edited sale {sale_id}: quantity {old_qty} -> {new_quantity}")

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Sale updated successfully!'})
        flash('Sale updated and inventory adjusted.', 'success')

    except Exception as e:
        logger.error("Edit sale error: %s", e)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'An unexpected error occurred.'}), 500
        flash('An unexpected error occurred.', 'danger')

    return redirect(url_for('sales.sales_dashboard'))


@sales_bp.route('/sales/delete/<int:sale_id>', methods=['POST'])
@admin_required
def delete_sale(sale_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT product_id, quantity FROM sale WHERE sale_id = %s", (sale_id,))
            sale = cursor.fetchone()

            if sale:
                cursor.execute("UPDATE product SET quantity = quantity + %s WHERE product_id = %s",
                              (sale['quantity'], sale['product_id']))
                cursor.execute("DELETE FROM sale WHERE sale_id = %s", (sale_id,))

        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Deleted sale {sale_id}")

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Sale deleted successfully!'})
        flash('Sale record deleted and inventory restored.', 'success')
    except Exception as e:
        logger.error("Delete sale error: %s", e)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'An unexpected error occurred.'}), 500
        flash('An unexpected error occurred.', 'danger')

    return redirect(url_for('sales.sales_dashboard'))


@sales_bp.route('/sales/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_sales():
    data = request.get_json()
    ids = data.get('ids', [])
    if not ids:
        return jsonify({'success': False, 'message': 'No sales selected.'}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            placeholders = ','.join(['%s'] * len(ids))
            cursor.execute(f"SELECT product_id, quantity FROM sale WHERE sale_id IN ({placeholders})", ids)
            sales = cursor.fetchall()
            for sale in sales:
                cursor.execute("UPDATE product SET quantity = quantity + %s WHERE product_id = %s",
                              (sale['quantity'], sale['product_id']))
            cursor.execute(f"DELETE FROM sale WHERE sale_id IN ({placeholders})", ids)
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Bulk deleted {len(ids)} sales")
        return jsonify({'success': True, 'message': f'{len(ids)} sales deleted and inventory restored.'})
    except Exception as e:
        logger.error("Bulk delete sales error: %s", e)
        return jsonify({'success': False, 'message': 'Bulk delete failed.'}), 500
