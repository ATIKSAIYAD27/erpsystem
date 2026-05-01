from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import pymysql
from datetime import datetime

finance_bp = Blueprint('finance', __name__)

from app.db import get_db_connection

@finance_bp.route('/finance')
def finance_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 1. Fetch recent expenses
            cursor.execute("SELECT * FROM expense ORDER BY date DESC LIMIT 50")
            expenses = cursor.fetchall()
            
            # 2. Financial Summary
            cursor.execute("SELECT SUM(amount) as total_expenses FROM expense")
            total_expenses = cursor.fetchone()['total_expenses'] or 0
            
            cursor.execute("SELECT SUM(total_amount) as total_revenue FROM sale")
            total_revenue = cursor.fetchone()['total_revenue'] or 0
            
            cursor.execute("SELECT SUM(net_pay) as total_payroll FROM payroll")
            total_payroll = cursor.fetchone()['total_payroll'] or 0
            
            net_profit = total_revenue - total_expenses - total_payroll

        conn.close()

        return render_template('finance.html', 
                               expenses=expenses, 
                               total_expenses=total_expenses,
                               total_revenue=total_revenue,
                               total_payroll=total_payroll,
                               net_profit=net_profit)

    except Exception as e:
        flash(f'Database error: {str(e)}', 'danger')
        return render_template('finance.html', expenses=[], total_expenses=0, total_revenue=0, total_payroll=0, net_profit=0)

@finance_bp.route('/finance/expense/add', methods=['POST'])
def add_expense():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    category = request.form.get('category')
    amount = request.form.get('amount')
    date = request.form.get('date') or datetime.now().strftime('%Y-%m-%d')
    description = request.form.get('description')

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO expense (category, amount, date, description)
                VALUES (%s, %s, %s, %s)
            """, (category, amount, date, description))
        conn.commit()
        conn.close()
        flash('Expense recorded successfully.', 'success')
    except Exception as e:
        flash(f'Error recording expense: {str(e)}', 'danger')

    return redirect(url_for('finance.finance_dashboard'))
