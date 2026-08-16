from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime
from app.db import get_db_connection
from app.utils import login_required, admin_required, manager_or_admin_required, log_audit
import logging

risk_bp = Blueprint('risk', __name__)
logger = logging.getLogger(__name__)

RISK_CATEGORIES = ['Financial', 'Operational', 'Strategic', 'Compliance', 'Reputational', 'Technology', 'Human Resource']
RISK_LEVELS = ['Low', 'Medium', 'High', 'Critical']
RISK_STATUS = ['Identified', 'Assessed', 'Mitigating', 'Monitoring', 'Resolved', 'Accepted']


@risk_bp.route('/risks')
@login_required
@manager_or_admin_required
def risk_list():
    status_filter = request.args.get('status', '')
    category_filter = request.args.get('category', '')

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            base_sql = """
                SELECT r.*, u.name as identified_by_name,
                       a.name as assigned_to_name
                FROM risk r
                LEFT JOIN users u ON r.identified_by = u.user_id
                LEFT JOIN users a ON r.assigned_to = a.user_id
                WHERE 1=1
            """
            params = []

            if status_filter:
                base_sql += " AND r.status = %s"
                params.append(status_filter)
            if category_filter:
                base_sql += " AND r.category = %s"
                params.append(category_filter)

            base_sql += " ORDER BY FIELD(r.risk_level, 'Critical', 'High', 'Medium', 'Low'), r.created_at DESC"

            cursor.execute(base_sql, params)
            risks = cursor.fetchall()

            cursor.execute("SELECT COUNT(*) as total FROM risk WHERE status != 'Resolved'")
            active_risks = cursor.fetchone()['total']

            cursor.execute("SELECT COUNT(*) as total FROM risk WHERE risk_level = 'Critical' AND status != 'Resolved'")
            critical = cursor.fetchone()['total']

            cursor.execute("SELECT COUNT(*) as total FROM risk WHERE risk_level = 'High' AND status != 'Resolved'")
            high = cursor.fetchone()['total']

            cursor.execute("SELECT user_id, name FROM users ORDER BY name")
            users = cursor.fetchall()

        conn.close()

        for r in risks:
            if r.get('identified_date'):
                r['identified_date'] = r['identified_date'].strftime('%d/%m/%Y')
            if r.get('created_at'):
                r['created_at'] = r['created_at'].strftime('%d/%m/%Y')

        return render_template('risks.html',
                               risks=risks, users=users,
                               categories=RISK_CATEGORIES, levels=RISK_LEVELS, statuses=RISK_STATUS,
                               active_risks=active_risks, critical=critical, high=high,
                               status_filter=status_filter, category_filter=category_filter)
    except Exception as e:
        logger.error("Risk list error: %s", e)
        flash('An error occurred.', 'danger')
        return render_template('risks.html', risks=[], users=[], categories=RISK_CATEGORIES,
                               levels=RISK_LEVELS, statuses=RISK_STATUS, active_risks=0, critical=0, high=0)


@risk_bp.route('/risks/add', methods=['POST'])
@login_required
@manager_or_admin_required
def add_risk():
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    category = request.form.get('category', '')
    risk_level = request.form.get('risk_level', 'Medium')
    probability = int(request.form.get('probability', 3) or 3)
    impact = int(request.form.get('impact', 3) or 3)
    assigned_to = request.form.get('assigned_to') or None
    mitigation_plan = request.form.get('mitigation_plan', '').strip()

    if not title:
        flash('Title required.', 'danger')
        return redirect(url_for('risk.risk_list'))

    risk_score = probability * impact

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO risk (title, description, category, risk_level, probability, impact,
                    risk_score, assigned_to, mitigation_plan, identified_by, identified_date, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURDATE(), 'Identified')
            """, (title, description, category, risk_level, probability, impact,
                  risk_score, assigned_to, mitigation_plan, session['user_id']))
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Identified risk: {title} (Score: {risk_score})")
        flash(f'Risk identified. Score: {risk_score}/25', 'success')
    except Exception as e:
        logger.error("Add risk error: %s", e)
        flash('An error occurred.', 'danger')

    return redirect(url_for('risk.risk_list'))


@risk_bp.route('/risks/<int:risk_id>/status', methods=['POST'])
@login_required
@manager_or_admin_required
def update_risk_status(risk_id):
    new_status = request.form.get('status')
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("UPDATE risk SET status = %s WHERE risk_id = %s", (new_status, risk_id))
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Updated risk #{risk_id} status to {new_status}")
        flash(f'Risk status updated to {new_status}.', 'success')
    except Exception as e:
        logger.error("Update risk status error: %s", e)
        flash('An error occurred.', 'danger')
    return redirect(url_for('risk.risk_list'))


@risk_bp.route('/risks/delete/<int:risk_id>', methods=['POST'])
@login_required
@admin_required
def delete_risk(risk_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM risk WHERE risk_id = %s", (risk_id,))
        conn.commit()
        conn.close()
        flash('Risk deleted.', 'success')
    except Exception as e:
        logger.error("Delete risk error: %s", e)
        flash('An error occurred.', 'danger')
    return redirect(url_for('risk.risk_list'))
