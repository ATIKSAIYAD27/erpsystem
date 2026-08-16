from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file
from app.db import get_db_connection
from app.utils import login_required, indian_currency
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from io import BytesIO
import datetime
import logging

selfservice_bp = Blueprint('selfservice', __name__)
logger = logging.getLogger(__name__)


@selfservice_bp.route('/my-dashboard')
@login_required
def my_dashboard():
    user_id = session['user_id']
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT e.*, u.name, u.email
                FROM employee e JOIN users u ON e.user_id = u.user_id
                WHERE e.user_id = %s
            """, (user_id,))
            employee = cursor.fetchone()

            if not employee:
                flash('No employee record found.', 'warning')
                return redirect(url_for('dashboard.dashboard'))

            emp_id = employee['emp_id']

            cursor.execute("""
                SELECT * FROM attendance
                WHERE emp_id = %s ORDER BY date DESC LIMIT 30
            """, (emp_id,))
            attendance = cursor.fetchall()

            cursor.execute("""
                SELECT * FROM leaves
                WHERE emp_id = %s ORDER BY created_at DESC LIMIT 10
            """, (emp_id,))
            leaves = cursor.fetchall()

            cursor.execute("""
                SELECT * FROM leave_balance
                WHERE emp_id = %s AND year = YEAR(CURDATE())
            """, (emp_id,))
            leave_balance = cursor.fetchall()

            cursor.execute("""
                SELECT * FROM payroll
                WHERE emp_id = %s ORDER BY year DESC, month DESC LIMIT 6
            """, (emp_id,))
            payroll = cursor.fetchall()

            cursor.execute("""
                SELECT COUNT(*) as present FROM attendance
                WHERE emp_id = %s AND MONTH(date) = MONTH(CURDATE()) AND status = 'Present'
            """, (emp_id,))
            present_days = cursor.fetchone()['present']

            cursor.execute("""
                SELECT COUNT(*) as pending FROM leaves
                WHERE emp_id = %s AND status = 'Pending'
            """, (emp_id,))
            pending_leaves = cursor.fetchone()['pending']

        conn.close()

        for l in leaves:
            if l.get('start_date'):
                l['start_date'] = l['start_date'].strftime('%d/%m/%Y')
            if l.get('end_date'):
                l['end_date'] = l['end_date'].strftime('%d/%m/%Y')
        total_payroll = sum(float(p.get('net_pay', 0) or 0) for p in payroll)
        total_hours = 0
        for a in attendance:
            if a.get('check_in') and a.get('check_out'):
                ci = a['check_in']
                co = a['check_out']
                if isinstance(ci, str):
                    ci = datetime.datetime.strptime(ci, '%H:%M:%S').time() if ':' in ci else datetime.datetime.strptime(ci, '%H:%M').time()
                if isinstance(co, str):
                    co = datetime.datetime.strptime(co, '%H:%M:%S').time() if ':' in co else datetime.datetime.strptime(co, '%H:%M').time()
                diff = datetime.datetime.combine(datetime.date.today(), co) - datetime.datetime.combine(datetime.date.today(), ci)
                total_hours += diff.total_seconds() / 3600
        curr_month_name = datetime.datetime.now().strftime('%B')

        return render_template('self_service.html',
                               employee=employee,
                               attendance_records=attendance,
                               leave_history=leaves,
                               leave_balances=leave_balance,
                               payroll_history=payroll,
                               total_payroll=total_payroll,
                               total_hours=total_hours,
                               month_name=curr_month_name,
                               present_days=present_days,
                               pending_leaves=pending_leaves)
    except Exception as e:
        logger.error("Self-service dashboard error: %s", e)
        flash('An error occurred.', 'danger')
        return redirect(url_for('dashboard.dashboard'))


@selfservice_bp.route('/my-payslip/<int:payroll_id>')
@login_required
def download_payslip(payroll_id):
    user_id = session['user_id']
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT pr.*, u.name as emp_name, e.job_title, e.emp_id, e.department
                FROM payroll pr
                JOIN employee e ON pr.emp_id = e.emp_id
                JOIN users u ON e.user_id = u.user_id
                WHERE pr.payroll_id = %s AND e.user_id = %s
            """, (payroll_id, user_id))
            pay = cursor.fetchone()

            if not pay:
                flash('Payslip not found.', 'danger')
                return redirect(url_for('selfservice.my_dashboard'))

            cursor.execute("SELECT * FROM company_settings LIMIT 1")
            company = cursor.fetchone()

        conn.close()

        company_name = company.get('company_name', 'Nexus ERP') if company else 'Nexus ERP'
        net_pay = float(pay['net_pay'])
        basic = round(net_pay * 0.50)
        hra = round(basic * 0.40)
        month_name = datetime.date(1900, pay['month'], 1).strftime('%B')

        buffer = BytesIO()
        c = pdf_canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        blue = colors.HexColor("#3b82f6")
        c.setFillColor(blue)
        c.rect(0, height - 60, width, 60, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(40, height - 35, company_name.upper())
        c.setFont("Helvetica", 10)
        c.drawString(40, height - 50, f"Payslip - {month_name} {pay['year']}")

        y = height - 100
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, "Employee Details")
        y -= 20
        c.setFont("Helvetica", 10)
        c.drawString(40, y, f"Name: {pay['emp_name']}")
        c.drawString(300, y, f"ID: {pay['emp_id']}")
        y -= 18
        c.drawString(40, y, f"Department: {pay['department'] or 'N/A'}")
        c.drawString(300, y, f"Designation: {pay['job_title'] or 'N/A'}")

        y -= 40
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, "Earnings")
        y -= 20
        c.setFont("Helvetica", 10)
        c.drawString(40, y, f"Basic: Rs. {basic:,.2f}")
        c.drawString(200, y, f"HRA: Rs. {hra:,.2f}")
        c.drawString(360, y, f"Other: Rs. {net_pay - basic - hra:,.2f}")

        y -= 30
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, "Deductions")
        y -= 20
        c.setFont("Helvetica", 10)
        c.drawString(40, y, f"Total Deductions: Rs. {float(pay['deductions']):,.2f}")

        y -= 40
        c.setFillColor(colors.HexColor("#10b981"))
        c.rect(40, y - 25, width - 80, 35, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(55, y - 15, f"NET PAY: Rs. {net_pay:,.2f}")

        c.showPage()
        c.save()
        buffer.seek(0)

        return send_file(buffer, as_attachment=True,
                         download_name=f"Payslip_{pay['emp_name']}_{pay['month']}_{pay['year']}.pdf",
                         mimetype='application/pdf')
    except Exception as e:
        logger.error("Download payslip error: %s", e)
        flash('Error generating payslip.', 'danger')
        return redirect(url_for('selfservice.my_dashboard'))
