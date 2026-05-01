from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import pymysql

product_bp = Blueprint('product', __name__)

from app.db import get_db_connection

@product_bp.route('/inventory')
def inventory_list():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    search_query = request.args.get('q', '')
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Fetch products with optional search
            if search_query:
                sql = """
                    SELECT product_id, name, sku, quantity, reorder_level, unit_price 
                    FROM product 
                    WHERE name LIKE %s OR sku LIKE %s
                    ORDER BY product_id DESC
                """
                cursor.execute(sql, (f'%{search_query}%', f'%{search_query}%'))
            else:
                sql = """
                    SELECT product_id, name, sku, quantity, reorder_level, unit_price 
                    FROM product 
                    ORDER BY product_id DESC
                """
                cursor.execute(sql)
            products = cursor.fetchall()
            
            # Identify low stock products for alerts
            low_stock_alerts = []
            total_inventory_value = 0
            
            for p in products:
                total_inventory_value += (p['quantity'] * p['unit_price'])
                if p['quantity'] <= p['reorder_level']:
                    low_stock_alerts.append(p)
                    
            # We could optionally log these to stock_alert table, but dynamic calculation is better for UI.

        conn.close()

        return render_template('inventory.html', 
                               products=products, 
                               low_stock_alerts=low_stock_alerts,
                               total_value=total_inventory_value)

    except Exception as e:
        flash(f'Database error: {str(e)}', 'danger')
        return render_template('inventory.html', products=[], low_stock_alerts=[], total_value=0)

@product_bp.route('/inventory/add', methods=['POST'])
def add_product():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    # Only Admin or Manager should ideally add products, but we'll allow it for now
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
        flash('Product added to inventory successfully.', 'success')

    except pymysql.err.IntegrityError:
        flash('A product with this SKU already exists.', 'danger')
    except Exception as e:
        flash(f'Error adding product: {str(e)}', 'danger')

    return redirect(url_for('product.inventory_list'))

@product_bp.route('/inventory/edit/<int:product_id>', methods=['POST'])
def edit_product(product_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

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
        flash('Product updated successfully.', 'success')
    except Exception as e:
        flash(f'Error updating product: {str(e)}', 'danger')

    return redirect(url_for('product.inventory_list'))

@product_bp.route('/inventory/delete/<int:product_id>')
def delete_product(product_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Check if product is used in sales
            cursor.execute("SELECT COUNT(*) as count FROM sale WHERE product_id = %s", (product_id,))
            if cursor.fetchone()['count'] > 0:
                flash('Cannot delete product as it has sales records associated with it.', 'warning')
                return redirect(url_for('product.inventory_list'))

            cursor.execute("DELETE FROM product WHERE product_id = %s", (product_id,))
        conn.commit()
        conn.close()
        flash('Product deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting product: {str(e)}', 'danger')

    return redirect(url_for('product.inventory_list'))
