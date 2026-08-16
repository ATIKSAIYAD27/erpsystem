from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.utils import login_required, admin_required, manager_or_admin_required, log_audit
import logging

product_bp = Blueprint('product', __name__)

logger = logging.getLogger(__name__)

from app.db import get_db_connection


@product_bp.route('/inventory')
@manager_or_admin_required
def inventory_list():
    search_query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    offset = (page - 1) * per_page
    sort_by = request.args.get('sort', 'product_id')
    sort_dir = request.args.get('dir', 'DESC')

    allowed_sorts = {'product_id', 'name', 'sku', 'quantity', 'unit_price'}
    if sort_by not in allowed_sorts:
        sort_by = 'product_id'
    if sort_dir not in ('ASC', 'DESC'):
        sort_dir = 'DESC'

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if search_query:
                cursor.execute("SELECT COUNT(*) as total FROM product WHERE name LIKE %s OR sku LIKE %s",
                    (f'%{search_query}%', f'%{search_query}%'))
                total = cursor.fetchone()['total']
                sql = f"""
                    SELECT product_id, name, sku, quantity, reorder_level, unit_price
                    FROM product
                    WHERE name LIKE %s OR sku LIKE %s
                    ORDER BY `{sort_by}` {sort_dir}
                    LIMIT %s OFFSET %s
                """
                cursor.execute(sql, (f'%{search_query}%', f'%{search_query}%', per_page, offset))
            else:
                cursor.execute("SELECT COUNT(*) as total FROM product")
                total = cursor.fetchone()['total']
                sql = f"""
                    SELECT product_id, name, sku, quantity, reorder_level, unit_price
                    FROM product
                    ORDER BY `{sort_by}` {sort_dir}
                    LIMIT %s OFFSET %s
                """
                cursor.execute(sql, (per_page, offset))
            products = cursor.fetchall()

            low_stock_alerts = []
            total_inventory_value = 0
            for p in products:
                total_inventory_value += (p['quantity'] * p['unit_price'])
                if p['quantity'] <= p['reorder_level']:
                    low_stock_alerts.append(p)

            cursor.execute("SELECT COUNT(*) as total FROM product WHERE quantity <= reorder_level")
            low_stock_count = cursor.fetchone()['total']

        conn.close()

        total_pages = (total + per_page - 1) // per_page

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'products': products,
                'low_stock_alerts': low_stock_alerts,
                'total_value': total_inventory_value,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages
            })

        return render_template('inventory.html', products=products,
                               low_stock_alerts=low_stock_alerts,
                               total_value=total_inventory_value,
                               page=page, per_page=per_page, total=total, total_pages=total_pages,
                               low_stock_count=low_stock_count)

    except Exception as e:
        logger.error("Inventory list error: %s", e)
        flash('An unexpected error occurred.', 'danger')
        return render_template('inventory.html', products=[], low_stock_alerts=[], total_value=0,
                               page=1, per_page=25, total=0, total_pages=0, low_stock_count=0)


@product_bp.route('/inventory/add', methods=['POST'])
@manager_or_admin_required
def add_product():
    name = request.form.get('name')
    sku = request.form.get('sku')
    quantity = request.form.get('quantity')
    reorder_level = request.form.get('reorder_level')
    unit_price = request.form.get('unit_price')

    if not all([name, sku, quantity, reorder_level, unit_price]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('product.inventory_list'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO product (name, sku, quantity, reorder_level, unit_price)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (name, sku, quantity, reorder_level, unit_price))
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Added product: {name} (SKU: {sku})")

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Product added successfully.'})
        flash('Product added to inventory successfully.', 'success')

    except Exception as e:
        logger.error("Add product error: %s", e)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'A product with this SKU may already exist.'}), 500
        flash('A product with this SKU may already exist.', 'danger')

    return redirect(url_for('product.inventory_list'))


@product_bp.route('/inventory/edit/<int:product_id>', methods=['POST'])
@manager_or_admin_required
def edit_product(product_id):
    name = request.form.get('name')
    sku = request.form.get('sku')
    quantity = request.form.get('quantity')
    reorder_level = request.form.get('reorder_level')
    unit_price = request.form.get('unit_price')

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
                UPDATE product
                SET name=%s, sku=%s, quantity=%s, reorder_level=%s, unit_price=%s
                WHERE product_id=%s
            """
            cursor.execute(sql, (name, sku, quantity, reorder_level, unit_price, product_id))
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Updated product {product_id}: {name}")

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Product updated successfully.'})
        flash('Product updated successfully.', 'success')
    except Exception as e:
        logger.error("Edit product error: %s", e)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'An unexpected error occurred.'}), 500
        flash('An unexpected error occurred.', 'danger')

    return redirect(url_for('product.inventory_list'))


@product_bp.route('/inventory/delete/<int:product_id>', methods=['POST'])
@admin_required
def delete_product(product_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM sale WHERE product_id = %s", (product_id,))
            if cursor.fetchone()['count'] > 0:
                flash('Cannot delete product as it has sales records associated with it.', 'warning')
                return redirect(url_for('product.inventory_list'))

            cursor.execute("SELECT name FROM product WHERE product_id = %s", (product_id,))
            product = cursor.fetchone()
            product_name = product['name'] if product else str(product_id)

            cursor.execute("DELETE FROM product WHERE product_id = %s", (product_id,))
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Deleted product {product_id}: {product_name}")

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Product deleted successfully.'})
        flash('Product deleted successfully.', 'success')
    except Exception as e:
        logger.error("Delete product error: %s", e)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'An unexpected error occurred.'}), 500
        flash('An unexpected error occurred.', 'danger')

    return redirect(url_for('product.inventory_list'))


@product_bp.route('/inventory/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_products():
    data = request.get_json()
    ids = data.get('ids', [])
    if not ids:
        return jsonify({'success': False, 'message': 'No products selected.'}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            placeholders = ','.join(['%s'] * len(ids))
            cursor.execute(f"DELETE FROM product WHERE product_id IN ({placeholders})", ids)
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Bulk deleted {len(ids)} products")
        return jsonify({'success': True, 'message': f'{len(ids)} products deleted.'})
    except Exception as e:
        logger.error("Bulk delete products error: %s", e)
        return jsonify({'success': False, 'message': 'Bulk delete failed.'}), 500


@product_bp.route('/inventory/bulk-update', methods=['POST'])
@manager_or_admin_required
def bulk_update_products():
    data = request.get_json()
    ids = data.get('ids', [])
    field = data.get('field')
    value = data.get('value')

    if not ids or field not in ('reorder_level', 'unit_price'):
        return jsonify({'success': False, 'message': 'Invalid bulk update request.'}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            placeholders = ','.join(['%s'] * len(ids))
            cursor.execute(f"UPDATE product SET {field} = %s WHERE product_id IN ({placeholders})",
                           [value] + ids)
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Bulk updated {field} for {len(ids)} products to {value}")
        return jsonify({'success': True, 'message': f'{len(ids)} products updated.'})
    except Exception as e:
        logger.error("Bulk update products error: %s", e)
        return jsonify({'success': False, 'message': 'Bulk update failed.'}), 500
