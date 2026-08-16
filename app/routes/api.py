from flask import Blueprint, request, jsonify, session, g
from functools import wraps
from werkzeug.security import check_password_hash
import hashlib
import time
import logging
from app.db import get_db_connection
from app.utils import login_required

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')
logger = logging.getLogger(__name__)


def _get_or_create_api_token(user_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT api_token FROM users WHERE user_id = %s", (user_id,))
            row = cursor.fetchone()
            if row and row.get('api_token'):
                conn.close()
                return row['api_token']
            token = hashlib.sha256(f"{user_id}-{time.time()}".encode()).hexdigest()
            cursor.execute("UPDATE users SET api_token=%s WHERE user_id=%s", (token, user_id))
        conn.commit()
        conn.close()
        return token
    except Exception as e:
        logger.error("Error generating API token: %s", e)
        return None


def api_auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        token = None
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]

        if not token:
            token = request.args.get('token')

        if not token:
            return jsonify({'error': 'Authentication required. Provide Bearer token or ?token= param.'}), 401

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT user_id, name, email, role_id FROM users WHERE api_token = %s",
                    (token,)
                )
                user = cursor.fetchone()
            conn.close()

            if not user:
                return jsonify({'error': 'Invalid or expired token.'}), 401

            g.api_user = user
        except Exception as e:
            logger.error("API auth error: %s", e)
            return jsonify({'error': 'Authentication error.'}), 500

        return f(*args, **kwargs)
    return decorated


def api_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        token = auth_header[7:] if auth_header.startswith('Bearer ') else request.args.get('token')

        if not token:
            return jsonify({'error': 'Authentication required.'}), 401

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT u.user_id, u.name, u.email, u.role_id, r.role_name
                       FROM users u LEFT JOIN role r ON u.role_id = r.role_id
                       WHERE u.api_token = %s""",
                    (token,)
                )
                user = cursor.fetchone()
            conn.close()

            if not user:
                return jsonify({'error': 'Invalid token.'}), 401
            if user.get('role_name') != 'Admin':
                return jsonify({'error': 'Admin access required.'}), 403

            g.api_user = user
        except Exception as e:
            logger.error("API admin auth error: %s", e)
            return jsonify({'error': 'Authentication error.'}), 500

        return f(*args, **kwargs)
    return decorated


@api_bp.route('/auth/token', methods=['POST'])
def get_token():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body must be JSON.'}), 400

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email and password are required.'}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT user_id, name, email, password_hash, role_id, role_name
                   FROM users u LEFT JOIN role r ON u.role_id = r.role_id
                   WHERE u.email = %s""",
                (email,)
            )
            user = cursor.fetchone()
        conn.close()

        if not user or not check_password_hash(user['password_hash'], password):
            return jsonify({'error': 'Invalid credentials.'}), 401

        token = _get_or_create_api_token(user['user_id'])
        return jsonify({
            'token': token,
            'user': {
                'id': user['user_id'],
                'name': user['name'],
                'email': user['email'],
                'role': user['role_name']
            }
        })
    except Exception as e:
        logger.error("Token generation error: %s", e)
        return jsonify({'error': 'Server error.'}), 500


@api_bp.route('/me', methods=['GET'])
@api_auth_required
def me():
    user = g.api_user
    return jsonify({
        'id': user['user_id'],
        'name': user['name'],
        'email': user['email']
    })


@api_bp.route('/employees', methods=['GET'])
@api_auth_required
def list_employees():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT e.emp_id, u.name, u.email, e.department, e.job_title, e.salary, e.hire_date
                FROM employee e JOIN users u ON e.user_id = u.user_id
                ORDER BY e.emp_id DESC
            """)
            employees = cursor.fetchall()
        conn.close()

        for emp in employees:
            for k, v in emp.items():
                if hasattr(v, 'isoformat'):
                    emp[k] = v.isoformat()
                elif isinstance(v, float):
                    emp[k] = str(v)

        return jsonify({'employees': employees, 'total': len(employees)})
    except Exception as e:
        logger.error("API employees error: %s", e)
        return jsonify({'error': 'Failed to fetch employees.'}), 500


@api_bp.route('/employees/<int:emp_id>', methods=['GET'])
@api_auth_required
def get_employee(emp_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT e.emp_id, u.name, u.email, e.department, e.job_title, e.salary, e.hire_date
                FROM employee e JOIN users u ON e.user_id = u.user_id
                WHERE e.emp_id = %s
            """, (emp_id,))
            emp = cursor.fetchone()
        conn.close()

        if not emp:
            return jsonify({'error': 'Employee not found.'}), 404

        for k, v in emp.items():
            if hasattr(v, 'isoformat'):
                emp[k] = v.isoformat()
            elif isinstance(v, float):
                emp[k] = str(v)

        return jsonify(emp)
    except Exception as e:
        logger.error("API employee error: %s", e)
        return jsonify({'error': 'Failed to fetch employee.'}), 500


@api_bp.route('/products', methods=['GET'])
@api_auth_required
def list_products():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM product ORDER BY product_id DESC")
            products = cursor.fetchall()
        conn.close()

        for p in products:
            for k, v in p.items():
                if hasattr(v, 'isoformat'):
                    p[k] = v.isoformat()
                elif isinstance(v, float):
                    p[k] = str(v)

        return jsonify({'products': products, 'total': len(products)})
    except Exception as e:
        logger.error("API products error: %s", e)
        return jsonify({'error': 'Failed to fetch products.'}), 500


@api_bp.route('/products/<int:product_id>', methods=['GET'])
@api_auth_required
def get_product(product_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM product WHERE product_id = %s", (product_id,))
            product = cursor.fetchone()
        conn.close()

        if not product:
            return jsonify({'error': 'Product not found.'}), 404

        for k, v in product.items():
            if hasattr(v, 'isoformat'):
                product[k] = v.isoformat()
            elif isinstance(v, float):
                product[k] = str(v)

        return jsonify(product)
    except Exception as e:
        logger.error("API product error: %s", e)
        return jsonify({'error': 'Failed to fetch product.'}), 500


@api_bp.route('/sales', methods=['GET'])
@api_auth_required
def list_sales():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT s.sale_id, s.quantity, s.total_amount, s.sale_date,
                       c.name as customer_name, p.name as product_name
                FROM sale s
                LEFT JOIN customer c ON s.customer_id = c.customer_id
                LEFT JOIN product p ON s.product_id = p.product_id
                ORDER BY s.sale_id DESC
            """)
            sales = cursor.fetchall()
        conn.close()

        for s in sales:
            for k, v in s.items():
                if hasattr(v, 'isoformat'):
                    s[k] = v.isoformat()
                elif isinstance(v, float):
                    s[k] = str(v)

        return jsonify({'sales': sales, 'total': len(sales)})
    except Exception as e:
        logger.error("API sales error: %s", e)
        return jsonify({'error': 'Failed to fetch sales.'}), 500


@api_bp.route('/dashboard', methods=['GET'])
@api_auth_required
def dashboard_stats():
    try:
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

            cursor.execute("SELECT SUM(amount) as total FROM expense")
            total_expenses = float(cursor.fetchone()['total'] or 0)

            cursor.execute("SELECT SUM(net_pay) as total FROM payroll")
            total_payroll = float(cursor.fetchone()['total'] or 0)

            cursor.execute("SELECT COUNT(*) as total FROM product WHERE quantity <= reorder_level")
            low_stock_count = int(cursor.fetchone()['total'])

        conn.close()

        return jsonify({
            'employees': total_employees,
            'products': total_products,
            'revenue': total_revenue,
            'pending_tasks': pending_tasks,
            'expenses': total_expenses,
            'payroll': total_payroll,
            'low_stock': low_stock_count
        })
    except Exception as e:
        logger.error("API dashboard error: %s", e)
        return jsonify({'error': 'Failed to fetch dashboard stats.'}), 500


@api_bp.route('/customers', methods=['GET'])
@api_auth_required
def list_customers():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM customer ORDER BY customer_id DESC")
            customers = cursor.fetchall()
        conn.close()
        return jsonify({'customers': customers, 'total': len(customers)})
    except Exception as e:
        logger.error("API customers error: %s", e)
        return jsonify({'error': 'Failed to fetch customers.'}), 500


@api_bp.route('/tasks', methods=['GET'])
@api_auth_required
def list_tasks():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT t.task_id, t.title, t.status, t.deadline, p.name as project_name,
                       u.name as assignee_name
                FROM task t
                LEFT JOIN project p ON t.project_id = p.project_id
                LEFT JOIN users u ON t.assigned_to = u.user_id
                ORDER BY t.task_id DESC
            """)
            tasks = cursor.fetchall()
        conn.close()

        for t in tasks:
            for k, v in t.items():
                if hasattr(v, 'isoformat'):
                    t[k] = v.isoformat()

        return jsonify({'tasks': tasks, 'total': len(tasks)})
    except Exception as e:
        logger.error("API tasks error: %s", e)
        return jsonify({'error': 'Failed to fetch tasks.'}), 500


@api_bp.route('/expenses', methods=['GET'])
@api_auth_required
def list_expenses():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT e.expense_id, e.category, e.amount, e.date, e.description,
                       u.name as created_by_name
                FROM expense e
                LEFT JOIN users u ON e.created_by = u.user_id
                ORDER BY e.expense_id DESC
            """)
            expenses = cursor.fetchall()
        conn.close()

        for ex in expenses:
            for k, v in ex.items():
                if hasattr(v, 'isoformat'):
                    ex[k] = v.isoformat()
                elif isinstance(v, float):
                    ex[k] = str(v)

        return jsonify({'expenses': expenses, 'total': len(expenses)})
    except Exception as e:
        logger.error("API expenses error: %s", e)
        return jsonify({'error': 'Failed to fetch expenses.'}), 500


@api_bp.route('/attendance', methods=['GET'])
@api_auth_required
def list_attendance():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT a.attendance_id, a.date, a.status, a.check_in, a.check_out,
                       u.name as employee_name
                FROM attendance a
                JOIN employee e ON a.emp_id = e.emp_id
                JOIN users u ON e.user_id = u.user_id
                ORDER BY a.date DESC, a.check_in DESC
                LIMIT 100
            """)
            records = cursor.fetchall()
        conn.close()

        for r in records:
            for k, v in r.items():
                if hasattr(v, 'isoformat'):
                    r[k] = v.isoformat()

        return jsonify({'attendance': records, 'total': len(records)})
    except Exception as e:
        logger.error("API attendance error: %s", e)
        return jsonify({'error': 'Failed to fetch attendance.'}), 500


@api_bp.route('/health', methods=['GET'])
def health():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        conn.close()
        return jsonify({'status': 'healthy', 'version': '1.0.0'})
    except Exception as e:
        return jsonify({'status': 'unhealthy'}), 503


@api_bp.route('/quotations', methods=['GET'])
@api_auth_required
def list_quotations():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT q.quote_id, q.quote_number, q.subject, q.grand_total, q.status,
                       q.created_at, q.valid_until, c.name as customer_name
                FROM quotation q
                LEFT JOIN customer c ON q.customer_id = c.customer_id
                ORDER BY q.created_at DESC
            """)
            quotations = cursor.fetchall()
        conn.close()

        for q in quotations:
            for k, v in q.items():
                if hasattr(v, 'isoformat'):
                    q[k] = v.isoformat()
                elif isinstance(v, float):
                    q[k] = str(v)

        return jsonify({'quotations': quotations, 'total': len(quotations)})
    except Exception as e:
        logger.error("API quotations error: %s", e)
        return jsonify({'error': 'Failed to fetch quotations.'}), 500


@api_bp.route('/quotations/<int:quote_id>', methods=['GET'])
@api_auth_required
def get_quotation(quote_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT q.*, c.name as customer_name, c.email as customer_email
                FROM quotation q
                LEFT JOIN customer c ON q.customer_id = c.customer_id
                WHERE q.quote_id = %s
            """, (quote_id,))
            quotation = cursor.fetchone()

            if not quotation:
                return jsonify({'error': 'Quotation not found.'}), 404

            cursor.execute("""
                SELECT qi.*, p.name as product_name
                FROM quotation_item qi
                LEFT JOIN product p ON qi.product_id = p.product_id
                WHERE qi.quote_id = %s
            """, (quote_id,))
            items = cursor.fetchall()
        conn.close()

        for k, v in quotation.items():
            if hasattr(v, 'isoformat'):
                quotation[k] = v.isoformat()
            elif isinstance(v, float):
                quotation[k] = str(v)

        for item in items:
            for k, v in item.items():
                if hasattr(v, 'isoformat'):
                    item[k] = v.isoformat()
                elif isinstance(v, float):
                    item[k] = str(v)

        return jsonify({'quotation': quotation, 'items': items})
    except Exception as e:
        logger.error("API quotation error: %s", e)
        return jsonify({'error': 'Failed to fetch quotation.'}), 500
