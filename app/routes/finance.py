from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from app.utils import login_required, admin_required, manager_or_admin_required, log_audit
import logging

finance_bp = Blueprint('finance', __name__)

logger = logging.getLogger(__name__)

from app.db import get_db_connection


@finance_bp.route('/finance')
@manager_or_admin_required
def finance_dashboard():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM expense ORDER BY date DESC LIMIT 50")
            expenses = cursor.fetchall()

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
        logger.error("Finance dashboard error: %s", e)
        flash('An unexpected error occurred.', 'danger')
        return render_template('finance.html', expenses=[], total_expenses=0, total_revenue=0, total_payroll=0, net_profit=0)


@finance_bp.route('/finance/expense/add', methods=['POST'])
@admin_required
def add_expense():
    category = request.form.get('category')
    department = request.form.get('department', '')
    amount = request.form.get('amount')
    date = request.form.get('date') or datetime.now().strftime('%Y-%m-%d')
    description = request.form.get('description')
    created_by = session.get('user_id')

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO expense (category, department, amount, date, description, created_by)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (category, department, amount, date, description, created_by))
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Added expense: {category} Rs.{amount}")
        flash('Expense recorded successfully.', 'success')
    except Exception as e:
        logger.error("Add expense error: %s", e)
        flash('An unexpected error occurred.', 'danger')

    return redirect(url_for('finance.finance_dashboard'))


@finance_bp.route('/finance/expense/edit/<int:expense_id>', methods=['POST'])
@admin_required
def edit_expense(expense_id):
    category = request.form.get('category')
    department = request.form.get('department', '')
    amount = request.form.get('amount')
    date = request.form.get('date')
    description = request.form.get('description')

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE expense
                SET category=%s, department=%s, amount=%s, date=%s, description=%s
                WHERE expense_id=%s
            """, (category, department, amount, date, description, expense_id))
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Edited expense {expense_id}: {category} Rs.{amount}")
        flash('Expense updated successfully.', 'success')
    except Exception as e:
        logger.error("Edit expense error: %s", e)
        flash('An unexpected error occurred.', 'danger')

    return redirect(url_for('finance.finance_dashboard'))


@finance_bp.route('/finance/expense/delete/<int:expense_id>', methods=['POST'])
@admin_required
def delete_expense(expense_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM expense WHERE expense_id = %s", (expense_id,))
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Deleted expense {expense_id}")
        flash('Expense deleted successfully.', 'success')
    except Exception as e:
        logger.error("Delete expense error: %s", e)
        flash('An unexpected error occurred.', 'danger')

    return redirect(url_for('finance.finance_dashboard'))
