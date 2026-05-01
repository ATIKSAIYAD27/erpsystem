from flask import Flask, session, redirect
import os

app = Flask(__name__)
app.secret_key = 'erpsystem_secret_key'

# Register Blueprints
from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.employee import employee_bp
from app.routes.product import product_bp
from app.routes.sales import sales_bp
from app.routes.project import project_bp
from app.routes.hr import hr_bp
from app.routes.finance import finance_bp
from app.routes.ai import ai_bp
from app.routes.reports import reports_bp
from app.routes.message import message_bp
from app.routes.profile import profile_bp
from app.routes.leave import leave_bp

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(employee_bp)
app.register_blueprint(product_bp)
app.register_blueprint(sales_bp)
app.register_blueprint(project_bp)
app.register_blueprint(hr_bp)
app.register_blueprint(finance_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(message_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(leave_bp)

@app.route('/')
def index():
    return redirect('/login')

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
        except:
            pass
    return dict(notif_count=notif_count, mail_count=mail_count, datetime=datetime.datetime, now=datetime.datetime.now())

# ✅ IMPORTANT: Deployment ke liye
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)