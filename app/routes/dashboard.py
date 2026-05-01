from flask import Blueprint, render_template, session, redirect, url_for, jsonify, request
from app.db import get_db_connection

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 1. Basic Stats
            cursor.execute("SELECT COUNT(*) as total FROM employee")
            total_employees = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as total FROM product")
            total_products = cursor.fetchone()['total']
            
            cursor.execute("SELECT SUM(total_amount) as total FROM sale")
            total_revenue = float(cursor.fetchone()['total'] or 0)
            
            cursor.execute("SELECT COUNT(*) as total FROM task WHERE status != 'Completed'")
            pending_tasks = int(cursor.fetchone()['total'])

            cursor.execute("SELECT COUNT(*) as total FROM users")
            total_users = int(cursor.fetchone()['total'])

            # 2. Advanced: Global Activity Feed (Union of Sales, Check-ins, and Tasks)
            cursor.execute("""
                (SELECT 'sale' as type, CONCAT('Sale of ', quantity, ' items recorded') as message, sale_date as timestamp FROM sale)
                UNION
                (SELECT 'attendance' as type, CONCAT('Employee #', emp_id, ' checked in') as message, CONCAT(`date`, ' ', check_in) as timestamp FROM attendance)
                UNION
                (SELECT 'task' as type, CONCAT('New task: ', title) as message, deadline as timestamp FROM task)
                ORDER BY timestamp DESC
                LIMIT 10
            """)
            recent_activity = cursor.fetchall()

        conn.close()

        return render_template('dashboard.html', 
                               total_employees=total_employees,
                               total_products=total_products,
                               total_revenue=total_revenue,
                               total_users=total_users,
                               pending_tasks=pending_tasks,
                               recent_activity=recent_activity)
    except Exception as e:
        return f"Database Error: {str(e)}"

@dashboard_bp.route('/notifications')
def notifications():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Fetch all notifications for the user
            cursor.execute("SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
            notifs = cursor.fetchall()
            
            # Mark all as read when viewed
            cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = %s", (session['user_id'],))
            conn.commit()
            
        conn.close()
        return render_template('notifications.html', notifications=notifs)
    except Exception as e:
        return f"Error: {str(e)}"

@dashboard_bp.route('/api/search')
def global_search():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify([])
        
    try:
        conn = get_db_connection()
        results = []
        with conn.cursor() as cursor:
            # Search Employees
            cursor.execute("""
                SELECT 'employee' as type, u.name as title, e.department as subtitle, e.emp_id as id 
                FROM employee e 
                JOIN users u ON e.user_id = u.user_id 
                WHERE u.name LIKE %s OR e.department LIKE %s
            """, (f'%{query}%', f'%{query}%'))
            results.extend(cursor.fetchall())
            
            # Search Products
            cursor.execute("""
                SELECT 'product' as type, name as title, sku as subtitle, product_id as id 
                FROM product 
                WHERE name LIKE %s OR sku LIKE %s
            """, (f'%{query}%', f'%{query}%'))
            results.extend(cursor.fetchall())
            
            # Search Tasks
            cursor.execute("""
                SELECT 'task' as type, title as title, status as subtitle, task_id as id 
                FROM task 
                WHERE title LIKE %s
            """, (f'%{query}%',))
            results.extend(cursor.fetchall())
            
        conn.close()
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

