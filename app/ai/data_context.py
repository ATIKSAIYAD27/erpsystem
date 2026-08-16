from app.db import get_db_connection
from datetime import datetime, timedelta


class DataContext:
    def __init__(self):
        self.conn = None

    def _connect(self):
        self.conn = get_db_connection()
        return self.conn.cursor()

    def _close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def get_sales_context(self, months=6):
        try:
            cursor = self._connect()
            try:
                cursor.execute("""
                    SELECT DATE_FORMAT(sale_date, '%%Y-%%m') as month,
                           SUM(total_amount) as revenue,
                           COUNT(*) as sale_count,
                           SUM(quantity) as units_sold
                    FROM sale
                    WHERE sale_date >= DATE_SUB(CURDATE(), INTERVAL %s MONTH)
                    GROUP BY DATE_FORMAT(sale_date, '%%Y-%%m')
                    ORDER BY month
                """, (months,))
                monthly_sales = cursor.fetchall()

                cursor.execute("""
                    SELECT p.name, SUM(s.quantity) as total_qty, SUM(s.total_amount) as total_revenue
                    FROM sale s JOIN product p ON s.product_id = p.product_id
                    GROUP BY p.name ORDER BY total_revenue DESC LIMIT 10
                """)
                top_products = cursor.fetchall()

                cursor.execute("""
                    SELECT c.name, SUM(s.total_amount) as total_spent, COUNT(*) as order_count
                    FROM sale s JOIN customer c ON s.customer_id = c.customer_id
                    GROUP BY c.name ORDER BY total_spent DESC LIMIT 10
                """)
                top_customers = cursor.fetchall()

                cursor.execute("SELECT SUM(total_amount) as total FROM sale")
                total_revenue = cursor.fetchone()['total'] or 0

                cursor.execute("""
                    SELECT SUM(total_amount) as today_revenue FROM sale
                    WHERE sale_date = CURDATE()
                """)
                today_revenue = cursor.fetchone()['today_revenue'] or 0
            finally:
                self._close()
            return {
                'monthly_sales': monthly_sales,
                'top_products': top_products,
                'top_customers': top_customers,
                'total_revenue': float(total_revenue),
                'today_revenue': float(today_revenue)
            }
        except Exception as e:
            self._close()
            return {'error': str(e)}

    def get_expense_context(self, months=6):
        try:
            cursor = self._connect()
            try:
                cursor.execute("""
                    SELECT DATE_FORMAT(date, '%%Y-%%m') as month,
                           category, SUM(amount) as total, COUNT(*) as count
                    FROM expense
                    WHERE date >= DATE_SUB(CURDATE(), INTERVAL %s MONTH)
                    GROUP BY DATE_FORMAT(date, '%%Y-%%m'), category
                    ORDER BY month, total DESC
                """, (months,))
                monthly_expenses = cursor.fetchall()

                cursor.execute("""
                    SELECT category, SUM(amount) as total, AVG(amount) as avg_amount,
                           MAX(amount) as max_amount, COUNT(*) as count
                    FROM expense
                    GROUP BY category ORDER BY total DESC
                """)
                category_breakdown = cursor.fetchall()

                cursor.execute("SELECT SUM(amount) as total FROM expense")
                total_expenses = cursor.fetchone()['total'] or 0

                cursor.execute("""
                    SELECT e.* FROM expense e
                    WHERE e.amount > (SELECT AVG(amount) * 2 FROM expense)
                    ORDER BY e.amount DESC LIMIT 5
                """)
                anomalies = cursor.fetchall()
            finally:
                self._close()
            return {
                'monthly_expenses': monthly_expenses,
                'category_breakdown': category_breakdown,
                'total_expenses': float(total_expenses),
                'anomalies': anomalies
            }
        except Exception as e:
            self._close()
            return {'error': str(e)}

    def get_inventory_context(self):
        try:
            cursor = self._connect()
            try:
                cursor.execute("""
                    SELECT product_id, name, sku, quantity, reorder_level, unit_price,
                           (quantity * unit_price) as stock_value,
                           CASE WHEN quantity <= reorder_level THEN 'LOW' ELSE 'OK' END as status
                    FROM product ORDER BY quantity ASC
                """)
                products = cursor.fetchall()

                cursor.execute("""
                    SELECT p.name, COALESCE(SUM(s.quantity), 0) as sold_30d
                    FROM product p
                    LEFT JOIN sale s ON p.product_id = s.product_id AND s.sale_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                    GROUP BY p.name ORDER BY sold_30d DESC LIMIT 10
                """)
                demand_30d = cursor.fetchall()

                cursor.execute("SELECT SUM(quantity * unit_price) as total_value FROM product")
                total_value = cursor.fetchone()['total_value'] or 0

                low_stock = [p for p in products if p['status'] == 'LOW']
            finally:
                self._close()
            return {
                'products': products,
                'demand_30d': demand_30d,
                'total_value': float(total_value),
                'low_stock_count': len(low_stock),
                'low_stock_products': low_stock
            }
        except Exception as e:
            self._close()
            return {'error': str(e)}

    def get_hr_context(self):
        try:
            cursor = self._connect()
            try:
                cursor.execute("SELECT COUNT(*) as total FROM employee")
                total_employees = cursor.fetchone()['total']

                cursor.execute("""
                    SELECT DATE_FORMAT(date, '%%Y-%%m') as month,
                           COUNT(DISTINCT emp_id) as present_count
                    FROM attendance
                    WHERE date >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH)
                    GROUP BY DATE_FORMAT(date, '%%Y-%%m')
                    ORDER BY month
                """)
                attendance_trend = cursor.fetchall()

                cursor.execute("""
                    SELECT status, COUNT(*) as count FROM leaves
                    WHERE month(created_at) = month(CURDATE())
                    GROUP BY status
                """)
                leave_summary = cursor.fetchall()

                cursor.execute("""
                    SELECT e.emp_id, u.name, e.department, e.job_title
                    FROM employee e JOIN users u ON e.user_id = u.user_id
                    LIMIT 20
                """)
                employees = cursor.fetchall()

                cursor.execute("SELECT SUM(net_pay) as total FROM payroll WHERE month = month(CURDATE())")
                current_payroll = cursor.fetchone()['total'] or 0
            finally:
                self._close()
            return {
                'total_employees': total_employees,
                'attendance_trend': attendance_trend,
                'leave_summary': leave_summary,
                'employees': employees,
                'current_payroll': float(current_payroll)
            }
        except Exception as e:
            self._close()
            return {'error': str(e)}

    def get_full_context(self):
        return {
            'sales': self.get_sales_context(),
            'expenses': self.get_expense_context(),
            'inventory': self.get_inventory_context(),
            'hr': self.get_hr_context()
        }

    def format_context_for_ai(self, context=None):
        if context is None:
            context = self.get_full_context()

        parts = []

        if 'sales' in context and 'error' not in context['sales']:
            s = context['sales']
            parts.append(f"SALES DATA:\n- Total Revenue: Rs.{s['total_revenue']:,.2f}\n- Today's Revenue: Rs.{s['today_revenue']:,.2f}")
            if s['top_products']:
                parts.append("Top Products: " + ", ".join([f"{p['name']} (Rs.{p['total_revenue']:,.0f})" for p in s['top_products'][:5]]))
            if s['monthly_sales']:
                parts.append("Monthly Trend: " + " → ".join([f"{m['month']}: Rs.{m['revenue']:,.0f}" for m in s['monthly_sales']]))

        if 'expenses' in context and 'error' not in context['expenses']:
            e = context['expenses']
            parts.append(f"\nEXPENSE DATA:\n- Total Expenses: Rs.{e['total_expenses']:,.2f}")
            if e['category_breakdown']:
                parts.append("By Category: " + ", ".join([f"{c['category']}: Rs.{c['total']:,.0f}" for c in e['category_breakdown'][:5]]))
            if e['anomalies']:
                parts.append(f"Anomalies Detected: {len(e['anomalies'])} unusual expenses")

        if 'inventory' in context and 'error' not in context['inventory']:
            inv = context['inventory']
            parts.append(f"\nINVENTORY DATA:\n- Total Products: {len(inv['products'])}\n- Inventory Value: Rs.{inv['total_value']:,.2f}\n- Low Stock Items: {inv['low_stock_count']}")
            if inv['low_stock_products']:
                parts.append("Low Stock: " + ", ".join([f"{p['name']} ({p['quantity']} left)" for p in inv['low_stock_products'][:5]]))

        if 'hr' in context and 'error' not in context['hr']:
            h = context['hr']
            parts.append(f"\nHR DATA:\n- Total Employees: {h['total_employees']}\n- Current Payroll: Rs.{h['current_payroll']:,.2f}")

        return "\n".join(parts)
