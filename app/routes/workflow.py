from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime
from app.db import get_db_connection
from app.utils import login_required, admin_required, manager_or_admin_required, log_audit, create_notification
import logging

workflow_bp = Blueprint('workflow', __name__)
logger = logging.getLogger(__name__)


@workflow_bp.route('/workflows')
@login_required
@manager_or_admin_required
def workflow_list():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT w.*, u.name as created_by_name,
                       (SELECT COUNT(*) FROM workflow_request wr WHERE wr.workflow_id = w.workflow_id AND wr.status = 'Pending') as pending_count
                FROM workflow w
                LEFT JOIN users u ON w.created_by = u.user_id
                ORDER BY w.created_at DESC
            """)
            workflows = cursor.fetchall()

            cursor.execute("""
                SELECT wr.*, w.name as workflow_name, u.name as requested_by_name,
                       a.name as approved_by_name
                FROM workflow_request wr
                LEFT JOIN workflow w ON wr.workflow_id = w.workflow_id
                LEFT JOIN users u ON wr.requested_by = u.user_id
                LEFT JOIN users a ON wr.approved_by = a.user_id
                ORDER BY wr.created_at DESC
                LIMIT 50
            """)
            requests_list = cursor.fetchall()

        conn.close()

        for w in workflows:
            if w.get('created_at'):
                w['created_at'] = w['created_at'].strftime('%d/%m/%Y')
        for r in requests_list:
            if r.get('created_at'):
                r['created_at'] = r['created_at'].strftime('%d/%m/%Y %H:%M')

        return render_template('workflows.html', workflows=workflows, requests=requests_list)
    except Exception as e:
        logger.error("Workflow list error: %s", e)
        flash('An error occurred.', 'danger')
        return render_template('workflows.html', workflows=[], requests=[])


@workflow_bp.route('/workflows/create', methods=['POST'])
@login_required
@admin_required
def create_workflow():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    trigger_type = request.form.get('trigger_type', 'manual')
    threshold = float(request.form.get('threshold', 0) or 0)
    approver_role = request.form.get('approver_role', 'Admin')

    if not name:
        flash('Workflow name required.', 'danger')
        return redirect(url_for('workflow.workflow_list'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO workflow (name, description, trigger_type, threshold_amount, approver_role, created_by)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, description, trigger_type, threshold, approver_role, session['user_id']))
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Created workflow: {name}")
        flash(f'Workflow "{name}" created.', 'success')
    except Exception as e:
        logger.error("Create workflow error: %s", e)
        flash('An error occurred.', 'danger')

    return redirect(url_for('workflow.workflow_list'))


@workflow_bp.route('/workflows/request', methods=['POST'])
@login_required
def submit_request():
    workflow_id = request.form.get('workflow_id')
    entity_type = request.form.get('entity_type', '')
    entity_id = request.form.get('entity_id', 0)
    amount = float(request.form.get('amount', 0) or 0)
    notes = request.form.get('notes', '').strip()

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO workflow_request (workflow_id, entity_type, entity_id, amount, notes, requested_by, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'Pending')
            """, (workflow_id, entity_type, entity_id, amount, notes, session['user_id']))

            cursor.execute("SELECT name FROM workflow WHERE workflow_id = %s", (workflow_id,))
            wf = cursor.fetchone()
            wf_name = wf['name'] if wf else 'Unknown'

            cursor.execute("SELECT user_id FROM users WHERE role_id = (SELECT role_id FROM role WHERE role_name = 'Admin')")
            admins = cursor.fetchall()
            for admin in admins:
                create_notification(admin['user_id'], f"New approval request: {wf_name} (Rs. {amount:,.2f}) from {session.get('name')}", 'warning')

        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Submitted workflow request: {wf_name}")
        flash('Request submitted for approval.', 'success')
    except Exception as e:
        logger.error("Submit request error: %s", e)
        flash('An error occurred.', 'danger')

    return redirect(url_for('workflow.workflow_list'))


@workflow_bp.route('/workflows/approve/<int:request_id>', methods=['POST'])
@login_required
@manager_or_admin_required
def approve_request(request_id):
    action = request.form.get('action', 'approve')
    new_status = 'Approved' if action == 'approve' else 'Rejected'

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE workflow_request
                SET status = %s, approved_by = %s, approved_at = NOW()
                WHERE request_id = %s AND status = 'Pending'
            """, (new_status, session['user_id'], request_id))

            cursor.execute("SELECT requested_by FROM workflow_request WHERE request_id = %s", (request_id,))
            req = cursor.fetchone()
            if req:
                create_notification(req['requested_by'], f"Your request has been {new_status.lower()} by {session.get('name')}", 'success' if new_status == 'Approved' else 'danger')

        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"{'Approved' if new_status == 'Approved' else 'Rejected'} workflow request #{request_id}")
        flash(f'Request {new_status.lower()}.', 'success')
    except Exception as e:
        logger.error("Approve request error: %s", e)
        flash('An error occurred.', 'danger')

    return redirect(url_for('workflow.workflow_list'))


@workflow_bp.route('/workflows/delete/<int:workflow_id>', methods=['POST'])
@login_required
@admin_required
def delete_workflow(workflow_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM workflow WHERE workflow_id = %s", (workflow_id,))
        conn.commit()
        conn.close()
        flash('Workflow deleted.', 'success')
    except Exception as e:
        logger.error("Delete workflow error: %s", e)
        flash('An error occurred.', 'danger')
    return redirect(url_for('workflow.workflow_list'))
