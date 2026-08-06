from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import pymysql
from app.db import get_db_connection
from app.utils import login_required, log_audit, create_notification

message_bp = Blueprint('message', __name__)

@message_bp.route('/mail')
@login_required
def inbox():
    user_id = session['user_id']
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE messages SET is_read = 1 
                WHERE receiver_id = %s AND is_read = 0
            """, (user_id,))
            conn.commit()

            cursor.execute("""
                SELECT m.*, u.name as sender_name, u.email as sender_email 
                FROM messages m
                JOIN users u ON m.sender_id = u.user_id
                WHERE m.receiver_id = %s
                ORDER BY m.created_at DESC
            """, (user_id,))
            inbox_messages = cursor.fetchall()
            
            cursor.execute("""
                SELECT m.*, u.name as receiver_name, u.email as receiver_email 
                FROM messages m
                JOIN users u ON m.receiver_id = u.user_id
                WHERE m.sender_id = %s
                ORDER BY m.created_at DESC
            """, (user_id,))
            sent_messages = cursor.fetchall()
            
            cursor.execute("SELECT user_id, name, email FROM users WHERE user_id != %s", (user_id,))
            users = cursor.fetchall()
            
        conn.close()
        return render_template('mail.html', inbox=inbox_messages, sent=sent_messages, users=users)
    except Exception as e:
        flash(f'Mail Error: {str(e)}', 'danger')
        return redirect(url_for('dashboard.dashboard'))

@message_bp.route('/mail/send', methods=['POST'])
@login_required
def send_message():
    sender_id = session['user_id']
    receiver_id = request.form.get('receiver_id')
    subject = request.form.get('subject')
    body = request.form.get('body')
    
    if not all([receiver_id, subject, body]):
        flash('Please fill all fields.', 'warning')
        return redirect(url_for('message.inbox'))
        
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO messages (sender_id, receiver_id, subject, content)
                VALUES (%s, %s, %s, %s)
            """, (sender_id, receiver_id, subject, body))
        conn.commit()
        conn.close()

        create_notification(receiver_id, f"New message from {session.get('name', 'someone')}: {subject}", 'info')
        log_audit(sender_id, f"Sent message to user {receiver_id}: {subject}")
        flash('Message sent successfully!', 'success')
    except Exception as e:
        flash(f'Error sending mail: {str(e)}', 'danger')
        
    return redirect(url_for('message.inbox'))

@message_bp.route('/mail/reply/<int:message_id>', methods=['POST'])
@login_required
def reply_message(message_id):
    user_id = session['user_id']

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT m.*, u.name as sender_name 
                FROM messages m
                JOIN users u ON m.sender_id = u.user_id
                WHERE m.message_id = %s
            """, (message_id,))
            original = cursor.fetchone()

            if not original:
                flash('Original message not found.', 'danger')
                return redirect(url_for('message.inbox'))

            receiver_id = original['sender_id']
            subject = f"Re: {original['subject']}" if original['subject'] else "Re: Your message"
            body = request.form.get('body')

            if not body:
                flash('Reply body cannot be empty.', 'warning')
                return redirect(url_for('message.inbox'))

            quoted_content = f"\n\n--- Original Message ---\n{original['content']}"
            full_body = body + quoted_content

            cursor.execute("""
                INSERT INTO messages (sender_id, receiver_id, subject, content)
                VALUES (%s, %s, %s, %s)
            """, (user_id, receiver_id, subject, full_body))
        conn.commit()
        conn.close()

        create_notification(receiver_id, f"Reply from {session.get('name', 'someone')}: {subject}", 'info')
        log_audit(user_id, f"Replied to message {message_id}")
        flash('Reply sent successfully!', 'success')
    except Exception as e:
        flash(f'Error sending reply: {str(e)}', 'danger')

    return redirect(url_for('message.inbox'))

@message_bp.route('/mail/delete/<int:message_id>', methods=['POST'])
@login_required
def delete_message(message_id):
    user_id = session['user_id']

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT sender_id, receiver_id FROM messages WHERE message_id = %s
            """, (message_id,))
            msg = cursor.fetchone()

            if not msg:
                flash('Message not found.', 'danger')
                return redirect(url_for('message.inbox'))

            if msg['sender_id'] != user_id and msg['receiver_id'] != user_id:
                flash('You do not have permission to delete this message.', 'danger')
                return redirect(url_for('message.inbox'))

            cursor.execute("DELETE FROM messages WHERE message_id = %s", (message_id,))
        conn.commit()
        conn.close()
        log_audit(user_id, f"Deleted message {message_id}")
        flash('Message deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting message: {str(e)}', 'danger')

    return redirect(url_for('message.inbox'))
