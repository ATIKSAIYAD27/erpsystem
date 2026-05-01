from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import pymysql
from app.db import get_db_connection

message_bp = Blueprint('message', __name__)

@message_bp.route('/mail')
def inbox():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Fetch Inbox
            cursor.execute("""
                SELECT m.*, u.name as sender_name, u.email as sender_email 
                FROM messages m
                JOIN users u ON m.sender_id = u.user_id
                WHERE m.receiver_id = %s
                ORDER BY m.created_at DESC
            """, (user_id,))
            inbox_messages = cursor.fetchall()
            
            # Fetch Sent
            cursor.execute("""
                SELECT m.*, u.name as receiver_name, u.email as receiver_email 
                FROM messages m
                JOIN users u ON m.receiver_id = u.user_id
                WHERE m.sender_id = %s
                ORDER BY m.created_at DESC
            """, (user_id,))
            sent_messages = cursor.fetchall()
            
            # Fetch Users for Compose dropdown
            cursor.execute("SELECT user_id, name, email FROM users WHERE user_id != %s", (user_id,))
            users = cursor.fetchall()
            
        conn.close()
        return render_template('mail.html', inbox=inbox_messages, sent=sent_messages, users=users)
    except Exception as e:
        flash(f'Mail Error: {str(e)}', 'danger')
        return redirect(url_for('dashboard.index'))

@message_bp.route('/mail/send', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
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
                INSERT INTO messages (sender_id, receiver_id, subject, body)
                VALUES (%s, %s, %s, %s)
            """, (sender_id, receiver_id, subject, body))
        conn.commit()
        conn.close()
        flash('Message sent successfully!', 'success')
    except Exception as e:
        flash(f'Error sending mail: {str(e)}', 'danger')
        
    return redirect(url_for('message.inbox'))
