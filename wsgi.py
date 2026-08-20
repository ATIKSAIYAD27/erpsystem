from gevent import monkey
monkey.patch_all()

from flask import Flask, session, redirect, render_template, jsonify
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO, emit, join_room
from flask_compress import Compress
from app.utils import indian_currency, indian_number, indian_date
from app.cache import cache
from app.tasks import task_manager
import os
import logging
import datetime
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            static_folder=os.path.join(BASE_DIR, 'app', 'static'),
            template_folder=os.path.join(BASE_DIR, 'templates'))

_secret = os.environ.get('SECRET_KEY')
if not _secret:
    raise RuntimeError("SECRET_KEY environment variable is required. Set it in .env or environment.")
app.secret_key = _secret

app.permanent_session_lifetime = timedelta(minutes=30)

csrf = CSRFProtect(app)
compress = Compress(app)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per minute"],
    storage_uri="memory://",
)

handler = RotatingFileHandler('server.log', maxBytes=5_000_000, backupCount=3)
handler.setLevel(logging.INFO)
handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s %(name)s: %(message)s'
))
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', logger=False, engineio_logger=False)

def _auto_init_db():
    try:
        from init_db_pg import init_db
        init_db()
        app.logger.info("Database tables verified/created automatically.")
    except Exception as e:
        app.logger.error("Auto DB init failed: %s", e)

_auto_init_db()

from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.employee import employee_bp
from app.routes.product import product_bp
from app.routes.sales import sales_bp
from app.routes.project import project_bp
from app.routes.hr import hr_bp
from app.routes.finance import finance_bp
from app.routes.reports import reports_bp
from app.routes.message import message_bp
from app.routes.profile import profile_bp
from app.routes.leave import leave_bp
from app.routes.customer import customer_bp
from app.routes.supplier import supplier_bp
from app.routes.purchase_order import po_bp
from app.routes.audit import audit_bp
from app.routes.company_settings import settings_bp
from app.routes.expense_report import expense_report_bp
from app.routes.ai_assistant import ai_bp
from app.routes.ai_analytics import ai_analytics_bp
from app.routes.twofa import twofa_bp
from app.routes.api import api_bp
from app.routes.documents import documents_bp
from app.routes.quotation import quotation_bp
from app.routes.calendar import calendar_bp
from app.routes.data_io import data_io_bp
from app.routes.barcode import barcode_bp
from app.routes.budget import budget_bp
from app.routes.workflow import workflow_bp
from app.routes.selfservice import selfservice_bp
from app.routes.risk import risk_bp
from app.routes.finance_enhanced import finance_enhanced_bp
from app.routes.sales_enhanced import sales_enhanced_bp

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(employee_bp)
app.register_blueprint(product_bp)
app.register_blueprint(sales_bp)
app.register_blueprint(project_bp)
app.register_blueprint(hr_bp)
app.register_blueprint(finance_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(message_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(leave_bp)
app.register_blueprint(customer_bp)
app.register_blueprint(supplier_bp)
app.register_blueprint(po_bp)
app.register_blueprint(audit_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(expense_report_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(ai_analytics_bp)
app.register_blueprint(twofa_bp)
app.register_blueprint(api_bp)
app.register_blueprint(documents_bp)
app.register_blueprint(quotation_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(data_io_bp)
app.register_blueprint(barcode_bp)
app.register_blueprint(budget_bp)
app.register_blueprint(workflow_bp)
app.register_blueprint(selfservice_bp)
app.register_blueprint(risk_bp)
app.register_blueprint(finance_enhanced_bp)
app.register_blueprint(sales_enhanced_bp)

app.jinja_env.filters['indian_currency'] = indian_currency
app.jinja_env.filters['indian_number'] = indian_number
app.jinja_env.filters['indian_date'] = indian_date


@app.route('/')
def index():
    return redirect('/login')


@app.route('/health')
def health_check():
    try:
        from app.db import get_db_connection
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        conn.close()
        cache_stats = cache.stats()
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'cache': cache_stats,
            'background_tasks': len(task_manager.get_all_tasks())
        }), 200
    except Exception as e:
        app.logger.error("Health check failed: %s", e)
        return jsonify({'status': 'unhealthy', 'database': 'disconnected'}), 503


@app.route('/api/system/performance')
def system_performance():
    """Internal API for system performance metrics."""
    try:
        return jsonify({
            'cache': cache.stats(),
            'tasks': task_manager.get_all_tasks(),
            'status': 'operational'
        })
    except Exception:
        return jsonify({'status': 'error'}), 500


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403


@app.errorhandler(413)
def request_entity_too_large(e):
    return render_template('413.html'), 413


@app.errorhandler(429)
def rate_limit_exceeded(e):
    return render_template('429.html'), 429


@app.errorhandler(500)
def internal_error(e):
    return render_template('500.html'), 500


@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


@app.context_processor
def inject_globals():
    notif_count = 0
    mail_count = 0
    if 'user_id' in session:
        cache_key = f"counts:{session['user_id']}"
        cached_counts = cache.get(cache_key)
        if cached_counts:
            notif_count = cached_counts.get('notif', 0)
            mail_count = cached_counts.get('mail', 0)
        else:
            conn = None
            try:
                from app.db import get_db_connection
                conn = get_db_connection()
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0", (session['user_id'],))
                    notif_count = cursor.fetchone()['count']
                    cursor.execute("SELECT COUNT(*) as count FROM messages WHERE receiver_id = %s AND is_read = 0", (session['user_id'],))
                    mail_count = cursor.fetchone()['count']
                cache.set(cache_key, {'notif': notif_count, 'mail': mail_count}, ttl=30)
            except Exception:
                pass
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
    return dict(
        notif_count=notif_count,
        mail_count=mail_count,
        datetime=datetime.datetime,
        now=datetime.datetime.now(),
        session=session
    )


@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        join_room(f"user_{session['user_id']}")
        if session.get('role_name') in ('Admin', 'Manager'):
            join_room('admins')


@socketio.on('disconnect')
def handle_disconnect():
    pass


@socketio.on('bulk_action')
def handle_bulk_action(data):
    """Handle bulk actions via WebSocket for real-time updates."""
    if 'user_id' not in session:
        return
    action = data.get('action')
    module = data.get('module')
    ids = data.get('ids', [])
    if action and module:
        emit('bulk_action_result', {
            'action': action,
            'module': module,
            'count': len(ids),
            'user': session.get('name', 'User')
        }, room='admins')


def emit_notification(user_id, message, msg_type='info'):
    socketio.emit('new_notification', {
        'message': message,
        'type': msg_type,
        'timestamp': str(datetime.datetime.now())
    }, room=f"user_{user_id}")


def emit_admin_notification(message, msg_type='info'):
    socketio.emit('new_notification', {
        'message': message,
        'type': msg_type,
        'timestamp': str(datetime.datetime.now())
    }, room='admins')


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    socketio.run(app, host="0.0.0.0", port=port, debug=debug, allow_unsafe_werkzeug=debug)
