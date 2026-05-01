import os
import google.generativeai as genai
from flask import Blueprint, request, jsonify, session
from dotenv import load_dotenv
from app.db import get_db_connection

load_dotenv()
ai_bp = Blueprint('ai', __name__)

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

def get_erp_context():
    """Fetch a snapshot of current ERP data to give AI context."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT SUM(total_amount) as rev FROM sale")
            revenue = cursor.fetchone()['rev'] or 0
            
            cursor.execute("SELECT COUNT(*) as count FROM product WHERE quantity <= reorder_level")
            low_stock = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM employee")
            emp_count = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM task WHERE status != 'Completed'")
            pending_tasks = cursor.fetchone()['count']
            
        conn.close()
        return f"Total Revenue: ${revenue:,.2f}, Low Stock Items: {low_stock}, Active Workforce: {emp_count}, Pending Tasks: {pending_tasks}."
    except:
        return "Context unavailable."

@ai_bp.route('/ai/ask', methods=['POST'])
def ask_ai():
    if 'user_id' not in session:
        return jsonify({'response': 'Please login first.'}), 401

    data = request.get_json()
    user_query = data.get('query', '')
    
    if not os.getenv("GEMINI_API_KEY"):
        return jsonify({'response': 'Please add your GEMINI_API_KEY to the .env file to enable deep thinking.'})

    context = get_erp_context()
    
    system_instruction = f"""
    You are the 'Nexus ERP Executive Strategist', a high-level business AI integrated into a premium ERP system.
    Current Business Context: {context}
    
    Guidelines:
    1. Be professional, strategic, and concise but insightful.
    2. Use the 'Current Business Context' to answer specifically about this company.
    3. If the user asks for ideas, give 3-5 actionable points.
    4. If they ask about data you don't have, explain what you DO know from the context.
    5. Be encouraging but realistic.
    """

    try:
        chat = model.start_chat(history=[])
        response = chat.send_message(f"{system_instruction}\n\nUser Question: {user_query}")
        return jsonify({'response': response.text})
    except Exception as e:
        return jsonify({'response': f"AI Brain Center Error: {str(e)}"}), 500

@ai_bp.route('/ai/analyze', methods=['GET'])
def analyze_business():
    # Keep the quick summary as a separate light-weight feature
    context = get_erp_context()
    try:
        response = model.generate_content(f"Based on these ERP stats: {context}, give a one-sentence high-level executive summary of business health.")
        return jsonify({'summary': response.text})
    except:
        return jsonify({'summary': "Business operations are active. Restock low items if necessary."})
