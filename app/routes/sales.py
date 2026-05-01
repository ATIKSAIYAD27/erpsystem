from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import pymysql
from datetime import datetime

sales_bp = Blueprint('sales', __name__)

from app.db import get_db_connection

@sales_bp.route('/sales')
def sales_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Fetch recent sales with customer and product details
            sql = """
                SELECT s.sale_id, s.quantity, s.total_amount, s.sale_date,
                       c.name as customer_name, p.name as product_name
                FROM sale s
                LEFT JOIN customer c ON s.customer_id = c.customer_id
                LEFT JOIN product p ON s.product_id = p.product_id
                ORDER BY s.sale_date DESC, s.sale_id DESC
                LIMIT 50
            """
            cursor.execute(sql)
            recent_sales = cursor.fetchall()
            
            # Fetch data for forms
            cursor.execute("SELECT customer_id, name FROM customer ORDER BY name")
            customers = cursor.fetchall()
            
            cursor.execute("SELECT product_id, name, unit_price, quantity as stock_left FROM product WHERE quantity > 0")
            products = cursor.fetchall()
            
            # Fetch total revenue
            cursor.execute("SELECT SUM(total_amount) as total FROM sale")
            total_revenue = cursor.fetchone()['total'] or 0

        conn.close()

        return render_template('sales.html', 
                               sales=recent_sales, 
                               customers=customers, 
                               products=products,
                               total_revenue=total_revenue)

    except Exception as e:
        flash(f'Database error: {str(e)}', 'danger')
        return render_template('sales.html', sales=[], customers=[], products=[], total_revenue=0)

@sales_bp.route('/sales/add', methods=['POST'])
def add_sale():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

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
            # 1. Fetch product price and check stock
            cursor.execute("SELECT unit_price, quantity FROM product WHERE product_id = %s", (product_id,))
            product = cursor.fetchone()
            
            if not product:
                flash('Invalid product selected.', 'danger')
                return redirect(url_for('sales.sales_dashboard'))
                
            if product['quantity'] < quantity:
                flash(f'Insufficient stock! Only {product["quantity"]} units available.', 'warning')
                return redirect(url_for('sales.sales_dashboard'))
                
            # 2. Calculate total amount
            total_amount = float(product['unit_price']) * quantity
            
            # 3. Insert Sale
            cursor.execute("""
                INSERT INTO sale (customer_id, product_id, quantity, total_amount, sale_date)
                VALUES (%s, %s, %s, %s, %s)
            """, (customer_id, product_id, quantity, total_amount, sale_date))
            
            # 4. Update Inventory (Deduct stock)
            cursor.execute("""
                UPDATE product 
                SET quantity = quantity - %s 
                WHERE product_id = %s
            """, (quantity, product_id))
            
        conn.commit()
        conn.close()
        flash(f'Sale recorded successfully! Inventory updated.', 'success')

    except Exception as e:
        flash(f'Error processing sale: {str(e)}', 'danger')

    return redirect(url_for('sales.sales_dashboard'))
