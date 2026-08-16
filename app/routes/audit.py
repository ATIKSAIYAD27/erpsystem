from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.db import get_db_connection
from app.utils import admin_required
import logging

audit_bp = Blueprint('audit', __name__)

logger = logging.getLogger(__name__)


@audit_bp.route('/audit-log')
@admin_required
def audit_log():
    search = request.args.get('search', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = """
                SELECT a.*, u.name as user_name
                FROM audit_log a
                LEFT JOIN users u ON a.user_id = u.user_id
                WHERE 1=1
            """
            params = []

            if search:
                query += " AND a.action LIKE %s"
                params.append(f'%{search}%')

            if start_date:
                query += " AND DATE(a.created_at) >= %s"
                params.append(start_date)

            if end_date:
                query += " AND DATE(a.created_at) <= %s"
                params.append(end_date)

            query += " ORDER BY a.created_at DESC LIMIT 200"

            cursor.execute(query, params)
            logs = cursor.fetchall()
        conn.close()

        return render_template('audit.html', logs=logs, search=search,
                               start_date=start_date, end_date=end_date)
    except Exception as e:
        logger.error("Audit log error: %s", e)
        flash('An unexpected error occurred.', 'danger')
        return redirect(url_for('dashboard.dashboard'))
