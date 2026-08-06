from flask import Blueprint, render_template, session, redirect, url_for, jsonify, request
from app.utils import login_required, log_audit
from app.ai.gemini_client import GeminiClient
from app.ai.data_context import DataContext

ai_bp = Blueprint('ai_assistant', __name__)


@ai_bp.route('/ai-chat')
@login_required
def ai_chat_page():
    return render_template('ai_chat.html')


@ai_bp.route('/api/ai/chat', methods=['POST'])
@login_required
def ai_chat():
    data = request.get_json()
    user_message = data.get('message', '').strip()

    if not user_message:
        return jsonify({'success': False, 'response': 'Please enter a message.'})

    try:
        ctx = DataContext()
        context_text = ctx.format_context_for_ai()

        client = GeminiClient()
        result = client.chat(user_message, context_text)

        log_audit(session['user_id'], f"AI Chat: {user_message[:80]}")

        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'response': f'Service error: {str(e)}'})


@ai_bp.route('/api/ai/expense/categorize', methods=['POST'])
@login_required
def categorize_expense():
    data = request.get_json()
    description = data.get('description', '')
    amount = float(data.get('amount', 0))

    try:
        from app.db import get_db_connection
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT category FROM expense")
            categories = [row['category'] for row in cursor.fetchall()]
        conn.close()

        if not categories:
            categories = ['Rent', 'Utilities', 'Salaries', 'Marketing', 'Office Supplies', 'Travel', 'Other']

        client = GeminiClient()
        result = client.categorize_expense(description, amount, categories)
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
