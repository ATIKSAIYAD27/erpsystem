from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime
from app.db import get_db_connection
from app.utils import login_required, manager_or_admin_required, admin_required, indian_currency
import logging

sales_enhanced_bp = Blueprint('sales_enhanced', __name__)
logger = logging.getLogger(__name__)

PIPELINE_STAGES = ['Lead', 'Qualified', 'Proposal', 'Negotiation', 'Closed Won', 'Closed Lost']


@sales_enhanced_bp.route('/sales/pipeline')
@login_required
@manager_or_admin_required
def sales_pipeline():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT sp.*, c.name as customer_name, u.name as owner_name
                FROM sales_pipeline sp
                LEFT JOIN customer c ON sp.customer_id = c.customer_id
                LEFT JOIN users u ON sp.owner_id = u.user_id
                ORDER BY CASE sp.stage
                    WHEN 'Lead' THEN 1 WHEN 'Qualified' THEN 2 WHEN 'Proposal' THEN 3
                    WHEN 'Negotiation' THEN 4 WHEN 'Closed Won' THEN 5 WHEN 'Closed Lost' THEN 6
                END, sp.created_at DESC
            """)
            deals = cursor.fetchall()

            cursor.execute("SELECT customer_id, name FROM customer ORDER BY name")
            customers = cursor.fetchall()

            cursor.execute("SELECT user_id, name FROM users ORDER BY name")
            users = cursor.fetchall()

            cursor.execute("""
                SELECT stage, COUNT(*) as count, SUM(deal_value) as value
                FROM sales_pipeline
                GROUP BY stage
            """)
            stage_summary = {row['stage']: {'count': row['count'], 'value': float(row['value'] or 0)} for row in cursor.fetchall()}

            cursor.execute("SELECT SUM(deal_value) as total FROM sales_pipeline WHERE stage NOT IN ('Closed Won', 'Closed Lost')")
            pipeline_value = float(cursor.fetchone()['total'] or 0)

            cursor.execute("SELECT SUM(deal_value) as total FROM sales_pipeline WHERE stage = 'Closed Won'")
            won_value = float(cursor.fetchone()['total'] or 0)

            cursor.execute("SELECT COUNT(*) as total FROM sales_pipeline WHERE stage = 'Closed Won'")
            won_count = cursor.fetchone()['total']

            cursor.execute("SELECT COUNT(*) as total FROM sales_pipeline WHERE stage NOT IN ('Closed Won', 'Closed Lost')")
            active_count = cursor.fetchone()['total']

        conn.close()

        for d in deals:
            if d.get('expected_close'):
                d['expected_close'] = d['expected_close'].strftime('%d/%m/%Y')
            if d.get('created_at'):
                d['created_at'] = d['created_at'].strftime('%d/%m/%Y')

        return render_template('sales_pipeline.html',
                               deals=deals, customers=customers, users=users,
                               stages=PIPELINE_STAGES,
                               stage_summary=stage_summary,
                               pipeline_value=pipeline_value,
                               won_value=won_value, won_count=won_count,
                               active_count=active_count)
    except Exception as e:
        logger.error("Sales pipeline error: %s", e)
        flash('An error occurred.', 'danger')
        return render_template('sales_pipeline.html', deals=[], customers=[], users=[],
                               stages=PIPELINE_STAGES, stage_summary={},
                               pipeline_value=0, won_value=0, won_count=0, active_count=0)


@sales_enhanced_bp.route('/sales/pipeline/add', methods=['POST'])
@login_required
@manager_or_admin_required
def add_deal():
    deal_name = request.form.get('deal_name', '').strip()
    customer_id = request.form.get('customer_id')
    deal_value = float(request.form.get('deal_value', 0) or 0)
    stage = request.form.get('stage', 'Lead')
    owner_id = request.form.get('owner_id', session['user_id'])
    expected_close = request.form.get('expected_close')
    notes = request.form.get('notes', '').strip()

    if not deal_name:
        flash('Deal name required.', 'danger')
        return redirect(url_for('sales_enhanced.sales_pipeline'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO sales_pipeline (deal_name, customer_id, deal_value, stage, owner_id, expected_close, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (deal_name, customer_id, deal_value, stage, owner_id, expected_close, notes))
        conn.commit()
        conn.close()
        flash(f'Deal "{deal_name}" created.', 'success')
    except Exception as e:
        logger.error("Add deal error: %s", e)
        flash('An error occurred.', 'danger')

    return redirect(url_for('sales_enhanced.sales_pipeline'))


@sales_enhanced_bp.route('/sales/pipeline/<int:deal_id>/stage', methods=['POST'])
@login_required
@manager_or_admin_required
def update_deal_stage(deal_id):
    new_stage = request.form.get('stage')
    if new_stage not in PIPELINE_STAGES:
        flash('Invalid stage.', 'danger')
        return redirect(url_for('sales_enhanced.sales_pipeline'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("UPDATE sales_pipeline SET stage = %s WHERE deal_id = %s", (new_stage, deal_id))
        conn.commit()
        conn.close()
        flash(f'Deal moved to {new_stage}.', 'success')
    except Exception as e:
        logger.error("Update deal stage error: %s", e)
        flash('An error occurred.', 'danger')

    return redirect(url_for('sales_enhanced.sales_pipeline'))


@sales_enhanced_bp.route('/sales/pipeline/delete/<int:deal_id>', methods=['POST'])
@login_required
@manager_or_admin_required
def delete_deal(deal_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM sales_pipeline WHERE deal_id = %s", (deal_id,))
        conn.commit()
        conn.close()
        flash('Deal deleted.', 'success')
    except Exception as e:
        logger.error("Delete deal error: %s", e)
        flash('An error occurred.', 'danger')
    return redirect(url_for('sales_enhanced.sales_pipeline'))


@sales_enhanced_bp.route('/api/sales/target', methods=['POST'])
@login_required
@admin_required
def set_target():
    data = request.get_json()
    month = data.get('month')
    year = data.get('year')
    target_amount = float(data.get('target', 0))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO sales_target (month, year, target_amount, set_by)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (month, year) DO UPDATE SET target_amount = EXCLUDED.target_amount
            """, (month, year, target_amount, session['user_id'], target_amount))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        logger.error("Set target error: %s", e)
        return jsonify({'error': 'Failed'}), 500
