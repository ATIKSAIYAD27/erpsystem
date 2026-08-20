from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta
from app.db import get_db_connection
from app.utils import login_required, admin_required, log_audit
import logging

calendar_bp = Blueprint('calendar', __name__)
logger = logging.getLogger(__name__)


@calendar_bp.route('/calendar')
@login_required
def calendar_view():
    return render_template('calendar.html')


@calendar_bp.route('/api/calendar/events')
@login_required
def calendar_events():
    start = request.args.get('start')
    end = request.args.get('end')

    try:
        conn = get_db_connection()
        events = []
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT l.leave_id as id, l.start_date as start, l.end_date as end,
                       CONCAT(u.name, ' - ', l.leave_type) as title,
                       CASE l.status
                           WHEN 'Approved' THEN '#10b981'
                           WHEN 'Rejected' THEN '#ef4444'
                           ELSE '#f59e0b'
                       END as color,
                       'leave' as type
                FROM leaves l
                JOIN employee e ON l.emp_id = e.emp_id
                JOIN users u ON e.user_id = u.user_id
                WHERE l.start_date >= %s AND l.end_date <= %s
            """, (start, end))
            events.extend(cursor.fetchall())

            cursor.execute("""
                SELECT t.task_id as id, t.deadline as start, t.deadline as end,
                       t.title,
                       CASE t.status
                           WHEN 'Completed' THEN '#10b981'
                           WHEN 'In Progress' THEN '#3b82f6'
                           WHEN 'Blocked' THEN '#ef4444'
                           ELSE '#f59e0b'
                       END as color,
                       'task' as type
                FROM task t
                WHERE t.deadline BETWEEN %s AND %s
            """, (start, end))
            events.extend(cursor.fetchall())

            if session.get('role_name') in ('Admin', 'Manager'):
                cursor.execute("""
                    SELECT po.po_id as id, po.order_date as start, po.expected_delivery as end,
                    CONCAT('PO: ', s.name) as title,
                    '#8b5cf6' as color,
                    'po' as type
                    FROM purchase_order po
                    JOIN supplier s ON po.supplier_id = s.supplier_id
                    WHERE po.order_date >= %s AND po.expected_delivery <= %s
                """, (start, end))
                events.extend(cursor.fetchall())

            cursor.execute("""
                SELECT q.quote_id as id, q.valid_until as start, q.valid_until as end,
                CONCAT(q.quote_number, ': ', q.subject) as title,
                CASE q.status
                    WHEN 'Accepted' THEN '#10b981'
                    WHEN 'Rejected' THEN '#ef4444'
                    WHEN 'Expired' THEN '#94a3b8'
                    ELSE '#3b82f6'
                END as color,
                'quotation' as type
                FROM quotation q
                WHERE q.valid_until BETWEEN %s AND %s
            """, (start, end))
            events.extend(cursor.fetchall())

        conn.close()

        for e in events:
            for k, v in e.items():
                if hasattr(v, 'isoformat'):
                    e[k] = v.isoformat()

        return jsonify(events)
    except Exception as e:
        logger.error("Calendar events error: %s", e)
        return jsonify([])


@calendar_bp.route('/api/calendar/event', methods=['POST'])
@login_required
def create_event():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400

    title = data.get('title', '').strip()
    start_date = data.get('start')
    end_date = data.get('end') or start_date
    event_type = data.get('type', 'event')

    if not title or not start_date:
        return jsonify({'error': 'Title and date required'}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO calendar_event (title, start_date, end_date, event_type, created_by)
                VALUES (%s, %s, %s, %s, %s)
            """, (title, start_date, end_date, event_type, session['user_id']))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        logger.error("Create event error: %s", e)
        return jsonify({'error': 'Failed'}), 500


@calendar_bp.route('/calendar/add-event', methods=['POST'])
@login_required
def create_event_form():
    title = request.form.get('title', '').strip()
    start_date = request.form.get('event_date')
    event_type = request.form.get('category', 'custom')

    if not title or not start_date:
        flash('Title and date are required.', 'danger')
        return redirect(url_for('calendar.calendar_view'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO calendar_event (title, start_date, end_date, event_type, created_by)
                VALUES (%s, %s, %s, %s, %s)
            """, (title, start_date, start_date, event_type, session['user_id']))
        conn.commit()
        conn.close()
        flash('Event added successfully.', 'success')
    except Exception as e:
        logger.error("Create event form error: %s", e)
        flash('Failed to add event.', 'danger')

    return redirect(url_for('calendar.calendar_view'))


@calendar_bp.route('/api/calendar/event/<int:event_id>', methods=['DELETE'])
@login_required
def delete_event(event_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM calendar_event WHERE event_id = %s AND created_by = %s", (event_id, session['user_id']))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        logger.error("Delete event error: %s", e)
        return jsonify({'error': 'Failed'}), 500
