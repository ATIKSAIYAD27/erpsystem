from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime
from app.db import get_db_connection
from app.utils import login_required, manager_or_admin_required, indian_currency
import logging

finance_enhanced_bp = Blueprint('finance_enhanced', __name__)
logger = logging.getLogger(__name__)


@finance_enhanced_bp.route('/finance/advanced')
@login_required
@manager_or_admin_required
def advanced_finance():
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT TO_CHAR(sale_date, 'YYYY-MM') as month, SUM(total_amount) as revenue
                FROM sale WHERE EXTRACT(YEAR FROM sale_date) = %s
                GROUP BY TO_CHAR(sale_date, 'YYYY-MM') ORDER BY month
            """, (year,))
            monthly_revenue = cursor.fetchall()

            cursor.execute("""
                SELECT TO_CHAR(date, 'YYYY-MM') as month, SUM(amount) as expenses
                FROM expense WHERE EXTRACT(YEAR FROM date) = %s
                GROUP BY TO_CHAR(date, 'YYYY-MM') ORDER BY month
            """, (year,))
            monthly_expenses = cursor.fetchall()

            cursor.execute("""
                SELECT category, SUM(amount) as total
                FROM expense WHERE EXTRACT(YEAR FROM date) = %s
                GROUP BY category ORDER BY total DESC
            """, (year,))
            expense_by_category = cursor.fetchall()

            cursor.execute("SELECT SUM(total_amount) as total FROM sale WHERE EXTRACT(YEAR FROM sale_date) = %s", (year,))
            total_revenue = float(cursor.fetchone()['total'] or 0)

            cursor.execute("SELECT SUM(amount) as total FROM expense WHERE EXTRACT(YEAR FROM date) = %s", (year,))
            total_expenses = float(cursor.fetchone()['total'] or 0)

            cursor.execute("SELECT SUM(net_pay) as total FROM payroll WHERE YEAR = %s", (year,))
            total_payroll = float(cursor.fetchone()['total'] or 0)

            net_profit = total_revenue - total_expenses - total_payroll

            cursor.execute("""
                SELECT TO_CHAR(sale_date, 'YYYY-MM') as month, SUM(total_amount) as revenue
                FROM sale WHERE sale_date >= CURRENT_DATE - INTERVAL '6 months'
                GROUP BY TO_CHAR(sale_date, 'YYYY-MM') ORDER BY month
            """)
            trend_data = cursor.fetchall()

            cursor.execute("""
                SELECT p.name as product_name, SUM(s.quantity) as qty, SUM(s.total_amount) as revenue
                FROM sale s JOIN product p ON s.product_id = p.product_id
                WHERE EXTRACT(YEAR FROM s.sale_date) = %s
                GROUP BY p.name ORDER BY revenue DESC LIMIT 10
            """, (year,))
            top_products = cursor.fetchall()

            cursor.execute("""
                SELECT c.name as customer_name, SUM(s.total_amount) as revenue
                FROM sale s JOIN customer c ON s.customer_id = c.customer_id
                WHERE EXTRACT(YEAR FROM s.sale_date) = %s
                GROUP BY c.name ORDER BY revenue DESC LIMIT 10
            """, (year,))
            top_customers = cursor.fetchall()

        conn.close()

        revenue_map = {row['month']: float(row['revenue']) for row in monthly_revenue}
        expense_map = {row['month']: float(row['expenses']) for row in monthly_expenses}
        months = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']

        profit_loss_data = []
        for m in months:
            key = f"{year}-{m}"
            r = revenue_map.get(key, 0)
            e = expense_map.get(key, 0)
            profit_loss_data.append({'month': key, 'revenue': r, 'expenses': e, 'profit': r - e})

        return render_template('finance_advanced.html',
                               year=year, month=month,
                               total_revenue=total_revenue,
                               total_expenses=total_expenses,
                               total_payroll=total_payroll,
                               net_profit=net_profit,
                               profit_loss_data=profit_loss_data,
                               expense_by_category=expense_by_category,
                               trend_data=trend_data,
                               top_products=top_products,
                               top_customers=top_customers)
    except Exception as e:
        logger.error("Advanced finance error: %s", e)
        flash('An error occurred.', 'danger')
        return redirect(url_for('finance.finance_dashboard'))


@finance_enhanced_bp.route('/api/finance/cashflow')
@login_required
def cashflow_data():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT TO_CHAR(sale_date, 'YYYY-MM') as month, SUM(total_amount) as inflow
                FROM sale WHERE sale_date >= CURRENT_DATE - INTERVAL '12 months'
                GROUP BY TO_CHAR(sale_date, 'YYYY-MM') ORDER BY month
            """)
            inflows = {row['month']: float(row['inflow']) for row in cursor.fetchall()}

            cursor.execute("""
                SELECT TO_CHAR(date, 'YYYY-MM') as month, SUM(amount) as outflow
                FROM expense WHERE date >= CURRENT_DATE - INTERVAL '12 months'
                GROUP BY TO_CHAR(date, 'YYYY-MM') ORDER BY month
            """)
            outflows = {row['month']: float(row['outflow']) for row in cursor.fetchall()}

        conn.close()

        all_months = sorted(set(list(inflows.keys()) + list(outflows.keys())))
        data = [{
            'month': m,
            'inflow': inflows.get(m, 0),
            'outflow': outflows.get(m, 0),
            'net': inflows.get(m, 0) - outflows.get(m, 0)
        } for m in all_months]

        return jsonify({'cashflow': data})
    except Exception as e:
        logger.error("Cashflow API error: %s", e)
        return jsonify({'error': 'Failed'}), 500
