from flask import Blueprint, render_template, session, redirect, url_for, jsonify, request, flash
from app.db import get_db_connection
from app.utils import login_required
from app.cache import cache, invalidate_cache
import logging

dashboard_bp = Blueprint('dashboard', __name__)

logger = logging.getLogger(__name__)


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    conn = None
    try:
        cache_key = f"dashboard:{session.get('user_id')}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return render_template('dashboard.html', **cached_data)

        conn = get_db_connection()
        with conn.cursor() as cursor:
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

            cursor.execute("SELECT COUNT(*) as total FROM product WHERE quantity <= reorder_level")
            low_stock_count = int(cursor.fetchone()['total'])

            cursor.execute("SELECT SUM(amount) as total FROM expense")
            total_expenses = float(cursor.fetchone()['total'] or 0)

            cursor.execute("SELECT SUM(net_pay) as total FROM payroll")
            total_payroll = float(cursor.fetchone()['total'] or 0)

            cursor.execute("""
                SELECT TO_CHAR(sale_date, 'YYYY-MM') as month, SUM(total_amount) as revenue
                FROM sale
                WHERE sale_date >= CURRENT_DATE - INTERVAL '6 months'
                GROUP BY TO_CHAR(sale_date, 'YYYY-MM')
                ORDER BY month
            """)
            monthly_sales = cursor.fetchall()

            cursor.execute("""
                (SELECT 'sale' as type, CONCAT('Sale of ', quantity, ' items recorded') as message, CAST(sale_date AS TEXT) as timestamp FROM sale)
                UNION ALL
                (SELECT 'attendance' as type, CONCAT('Employee #', emp_id, ' checked in') as message, CAST(CONCAT(date, ' ', COALESCE(check_in, '00:00:00')) AS TEXT) as timestamp FROM attendance)
                UNION ALL
                (SELECT 'task' as type, CONCAT('New task: ', title) as message, CAST(COALESCE(deadline, CURRENT_DATE) AS TEXT) as timestamp FROM task)
                ORDER BY timestamp DESC
                LIMIT 10
            """)
            recent_activity = cursor.fetchall()

        chart_labels = [row['month'] for row in monthly_sales]
        chart_data = [float(row['revenue']) for row in monthly_sales]
        net_profit = total_revenue - total_expenses - total_payroll

        data = dict(
            total_employees=total_employees,
            total_products=total_products,
            total_revenue=total_revenue,
            total_users=total_users,
            pending_tasks=pending_tasks,
            low_stock_count=low_stock_count,
            total_expenses=total_expenses,
            total_payroll=total_payroll,
            net_profit=net_profit,
            recent_activity=recent_activity,
            chart_labels=chart_labels,
            chart_data=chart_data
        )

        cache.set(cache_key, data, ttl=60)
        return render_template('dashboard.html', **data)
    except Exception as e:
        logger.error("Dashboard error: %s", e)
        return render_template('500.html'), 500
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@dashboard_bp.route('/dashboard/refresh')
@login_required
def refresh_dashboard():
    """API endpoint to force-refresh dashboard data via AJAX."""
    try:
        invalidate_cache(f"dashboard:{session.get('user_id')}")
        cache_key = f"dashboard:{session.get('user_id')}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return jsonify({'status': 'refreshed', 'data': cached_data})
        return jsonify({'status': 'refreshed'})
    except Exception as e:
        logger.error("Dashboard refresh error: %s", e)
        return jsonify({'error': 'Refresh failed'}), 500


@dashboard_bp.route('/api/dashboard/stream')
@login_required
def dashboard_stream():
    """SSE endpoint for live dashboard updates."""
    import json
    import time as _time
    from flask import Response

    def generate():
        last_hash = None
        for _ in range(300):
            try:
                from app.db import get_db_connection
                conn = get_db_connection()
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT SUM(total_amount) as total FROM sale")
                        revenue = float(cursor.fetchone()['total'] or 0)
                        cursor.execute("SELECT COUNT(*) as total FROM task WHERE status != 'Completed'")
                        tasks = int(cursor.fetchone()['total'])
                        cursor.execute("SELECT COUNT(*) as total FROM product WHERE quantity <= reorder_level")
                        low_stock = int(cursor.fetchone()['total'])
                finally:
                    conn.close()

                current_hash = f"{revenue}-{tasks}-{low_stock}"
                if current_hash != last_hash:
                    yield f"data: {json.dumps({'revenue': revenue, 'pending_tasks': tasks, 'low_stock': low_stock})}\n\n"
                    last_hash = current_hash
            except Exception:
                pass
            _time.sleep(5)

    return Response(generate(), mimetype='text/event-stream')


@dashboard_bp.route('/notifications')
@login_required
def notifications():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
            notifs = cursor.fetchall()

            cursor.execute("UPDATE notifications SET is_read = TRUE WHERE user_id = %s", (session['user_id'],))
            conn.commit()

        return render_template('notifications.html', notifications=notifs)
    except Exception as e:
        logger.error("Notifications error: %s", e)
        flash('An error occurred while loading notifications.', 'danger')
        return redirect(url_for('dashboard.dashboard'))
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@dashboard_bp.route('/api/search')
@login_required
def global_search():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify([])

    cache_key = f"search:{query}"
    cached_results = cache.get(cache_key)
    if cached_results:
        return jsonify(cached_results)

    conn = None
    try:
        conn = get_db_connection()
        results = []
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 'employee' as type, u.name as title, e.department as subtitle, e.emp_id as id
                FROM employee e
                JOIN users u ON e.user_id = u.user_id
                WHERE u.name LIKE %s OR e.department LIKE %s
                LIMIT 10
            """, (f'%{query}%', f'%{query}%'))
            results.extend(cursor.fetchall())

            cursor.execute("""
                SELECT 'product' as type, name as title, sku as subtitle, product_id as id
                FROM product
                WHERE name LIKE %s OR sku LIKE %s
                LIMIT 10
            """, (f'%{query}%', f'%{query}%'))
            results.extend(cursor.fetchall())

            cursor.execute("""
                SELECT 'task' as type, title as title, status as subtitle, task_id as id
                FROM task
                WHERE title LIKE %s
                LIMIT 10
            """, (f'%{query}%',))
            results.extend(cursor.fetchall())

        cache.set(cache_key, results, ttl=120)
        return jsonify(results)
    except Exception as e:
        logger.error("Search error: %s", e)
        return jsonify({'error': 'Search temporarily unavailable'}), 500
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
