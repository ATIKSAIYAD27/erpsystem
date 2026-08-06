from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file
from app.db import get_db_connection
from app.utils import login_required
from io import BytesIO
import csv

expense_report_bp = Blueprint('expense_report', __name__)

@expense_report_bp.route('/expense-reports')
@login_required
def expense_reports():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    total_revenue = 0
    total_expenses = 0
    total_payroll = 0
    net_profit = 0
    category_breakdown = []

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            date_filter = ""
            params = []

            if start_date:
                date_filter += " AND date >= %s"
                params.append(start_date)
            if end_date:
                date_filter += " AND date <= %s"
                params.append(end_date)

            cursor.execute(
                f"SELECT COALESCE(SUM(total_amount), 0) AS total FROM sale WHERE 1=1 {date_filter}",
                params
            )
            total_revenue = cursor.fetchone()['total']

            cursor.execute(
                f"SELECT COALESCE(SUM(amount), 0) AS total FROM expense WHERE 1=1 {date_filter}",
                params
            )
            total_expenses = cursor.fetchone()['total']

            cursor.execute("SELECT COALESCE(SUM(net_pay), 0) AS total FROM payroll")
            total_payroll = cursor.fetchone()['total']

            net_profit = total_revenue - total_expenses - total_payroll

            cursor.execute(
                f"SELECT category, SUM(amount) AS total FROM expense WHERE 1=1 {date_filter} GROUP BY category ORDER BY total DESC",
                params
            )
            category_breakdown = cursor.fetchall()

        conn.close()

        return render_template('expense_reports.html',
                               total_revenue=total_revenue,
                               total_expenses=total_expenses,
                               total_payroll=total_payroll,
                               net_profit=net_profit,
                               category_breakdown=category_breakdown,
                               start_date=start_date,
                               end_date=end_date)
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Error generating report: {str(e)}', 'danger')
        return redirect(url_for('dashboard.dashboard'))

@expense_report_bp.route('/expense-reports/export')
@login_required
def export_expenses():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = """
                SELECT e.date, e.category, e.amount, e.description, e.created_by
                FROM expense e
                WHERE 1=1
            """
            params = []

            if start_date:
                query += " AND e.date >= %s"
                params.append(start_date)
            if end_date:
                query += " AND e.date <= %s"
                params.append(end_date)

            query += " ORDER BY e.date DESC"

            cursor.execute(query, params)
            expenses = cursor.fetchall()
        conn.close()

        output = BytesIO()
        text_output = []
        writer = csv.writer(text_output)
        writer.writerow(['Date', 'Category', 'Amount', 'Description', 'Created By'])

        for exp in expenses:
            writer.writerow([
                exp['date'],
                exp['category'],
                exp['amount'],
                exp['description'] or '',
                exp['created_by'] or ''
            ])

        output.write('\n'.join(text_output).encode('utf-8'))
        output.seek(0)
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name='expense_report.csv'
        )
    except Exception as e:
        flash(f'Error exporting expenses: {str(e)}', 'danger')
        return redirect(url_for('expense_report.expense_reports'))
