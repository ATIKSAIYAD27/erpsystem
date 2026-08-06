from flask import Flask, session, redirect, render_template
import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'nexus_erp_secret_key_change_in_production_2024')
app.permanent_session_lifetime = timedelta(minutes=30)

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

@app.route('/')
def index():
    return redirect('/login')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template('500.html'), 500

from app.utils import indian_currency, indian_number, indian_date

app.jinja_env.filters['indian_currency'] = indian_currency
app.jinja_env.filters['indian_number'] = indian_number
app.jinja_env.filters['indian_date'] = indian_date

@app.context_processor
def inject_globals():
    import datetime
    notif_count = 0
    mail_count = 0
    if 'user_id' in session:
        try:
            from app.db import get_db_connection
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0", (session['user_id'],))
                notif_count = cursor.fetchone()['count']
                cursor.execute("SELECT COUNT(*) as count FROM messages WHERE receiver_id = %s AND is_read = 0", (session['user_id'],))
                mail_count = cursor.fetchone()['count']
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)