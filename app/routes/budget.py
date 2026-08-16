from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime
from app.db import get_db_connection
from app.utils import login_required, admin_required, manager_or_admin_required, log_audit, indian_currency
import logging

budget_bp = Blueprint('budget', __name__)
logger = logging.getLogger(__name__)


@budget_bp.route('/budgets')
@login_required
@manager_or_admin_required
def budget_list():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            year = int(request.args.get('year', datetime.now().year))

            cursor.execute("""
                SELECT b.*, u.name as created_by_name,
                       COALESCE(spent.total, 0) as spent_amount
                FROM budget b
                LEFT JOIN users u ON b.created_by = u.user_id
                LEFT JOIN (
                    SELECT department, SUM(amount) as total
                    FROM expense
                    WHERE YEAR(date) = %s
                    GROUP BY department
                ) spent ON spent.department = b.department
                WHERE b.fiscal_year = %s
                ORDER BY b.department
            """, (year, year))
            budgets = cursor.fetchall()

            cursor.execute("""
                SELECT department, SUM(amount) as total
                FROM expense
                WHERE YEAR(date) = %s
                GROUP BY department
            """, (year,))
            expenses = {row['department']: float(row['total']) for row in cursor.fetchall()}

            total_budget = sum(float(b['allocated_amount']) for b in budgets)
            total_spent = sum(float(b['spent_amount']) for b in budgets)

        conn.close()

        for b in budgets:
            b['spent_amount'] = expenses.get(b['department'], 0)
            b['utilization'] = (b['spent_amount'] / b['allocated_amount'] * 100) if b['allocated_amount'] > 0 else 0
            b['remaining'] = b['allocated_amount'] - b['spent_amount']

        return render_template('budgets.html',
                               budgets=budgets,
                               total_budget=total_budget,
                               total_spent=total_spent,
                               year=int(year))
    except Exception as e:
        logger.error("Budget list error: %s", e)
        flash('An error occurred.', 'danger')
        return render_template('budgets.html', budgets=[], total_budget=0, total_spent=0, year=datetime.now().year)


@budget_bp.route('/budgets/add', methods=['POST'])
@login_required
@admin_required
def add_budget():
    department = request.form.get('department', '').strip()
    allocated = float(request.form.get('allocated_amount', 0) or 0)
    year = int(request.form.get('fiscal_year', datetime.now().year))

    if not department or allocated <= 0:
        flash('Department and amount required.', 'danger')
        return redirect(url_for('budget.budget_list'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO budget (department, allocated_amount, fiscal_year, created_by)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE allocated_amount = %s
            """, (department, allocated, year, session['user_id'], allocated))
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Set budget for {department}: Rs.{allocated:,.2f} for {year}")
        flash(f'Budget set for {department}.', 'success')
    except Exception as e:
        logger.error("Add budget error: %s", e)
        flash('An error occurred.', 'danger')

    return redirect(url_for('budget.budget_list'))


@budget_bp.route('/budgets/delete/<int:budget_id>', methods=['POST'])
@login_required
@admin_required
def delete_budget(budget_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM budget WHERE budget_id = %s", (budget_id,))
        conn.commit()
        conn.close()
        flash('Budget deleted.', 'success')
    except Exception as e:
        logger.error("Delete budget error: %s", e)
        flash('An error occurred.', 'danger')
    return redirect(url_for('budget.budget_list'))


@budget_bp.route('/api/budgets/summary')
@login_required
def api_budget_summary():
    try:
        year = request.args.get('year', datetime.now().year)
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT b.department, b.allocated_amount,
                       COALESCE(spent.total, 0) as spent_amount
                FROM budget b
                LEFT JOIN (
                    SELECT department, SUM(amount) as total
                    FROM expense WHERE YEAR(date) = %s
                    GROUP BY department
                ) spent ON spent.department = b.department
                WHERE b.fiscal_year = %s
            """, (year, year))
            budgets = cursor.fetchall()
        conn.close()

        for b in budgets:
            for k, v in b.items():
                if isinstance(v, float):
                    b[k] = str(v)

        return jsonify({'budgets': budgets})
    except Exception as e:
        logger.error("API budget summary error: %s", e)
        return jsonify({'error': 'Failed'}), 500
