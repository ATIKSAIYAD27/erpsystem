from flask import Blueprint, send_file, session, abort
import pymysql
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from io import BytesIO
import datetime
import re
from app.utils import indian_currency

reports_bp = Blueprint('reports', __name__)

from app.db import get_db_connection


def amount_in_words(amount):
    ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven',
            'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve', 'Thirteen',
            'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
    tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty',
            'Seventy', 'Eighty', 'Ninety']

    if amount == 0:
        return "Indian Rupee Zero Only"

    def num_to_words(n):
        if n == 0:
            return ''
        elif n < 20:
            return ones[n]
        elif n < 100:
            return tens[n // 10] + (' ' + ones[n % 10] if n % 10 else '')
        elif n < 1000:
            return ones[n // 100] + ' Hundred' + (' and ' + num_to_words(n % 100) if n % 100 else '')
        elif n < 100000:
            return num_to_words(n // 1000) + ' Thousand' + (' ' + num_to_words(n % 1000) if n % 1000 else '')
        elif n < 10000000:
            return num_to_words(n // 100000) + ' Lakh' + (' ' + num_to_words(n % 100000) if n % 100000 else '')
        else:
            return num_to_words(n // 10000000) + ' Crore' + (' ' + num_to_words(n % 10000000) if n % 10000000 else '')

    int_part = int(amount)
    dec_part = round((amount - int_part) * 100)
    result = "Indian Rupee " + num_to_words(int_part)
    if dec_part > 0:
        result += " and " + num_to_words(dec_part) + " Paise"
    result += " Only"
    return result


@reports_bp.route('/report/invoice/<int:sale_id>')
def generate_invoice(sale_id):
    if 'user_id' not in session:
        abort(401)

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT s.*, c.name as customer_name, c.email as customer_email,
                       p.name as product_name, p.unit_price
                FROM sale s
                JOIN customer c ON s.customer_id = c.customer_id
                JOIN product p ON s.product_id = p.product_id
                WHERE s.sale_id = %s
            """, (sale_id,))
            sale = cursor.fetchone()

        if not sale:
            return "Invoice not found", 404

        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        p.setFont("Helvetica-Bold", 24)
        p.setFillColor(colors.HexColor("#3b82f6"))
        p.drawString(50, height - 80, "NEXUS ERP")

        p.setFont("Helvetica", 10)
        p.setFillColor(colors.black)
        p.drawString(50, height - 100, "123 Business Avenue, Tech City, India")
        p.drawString(50, height - 115, "Contact: +91 98765 43210")

        p.setFont("Helvetica-Bold", 16)
        p.drawString(400, height - 80, "INVOICE")
        p.setFont("Helvetica", 10)
        p.drawString(400, height - 100, f"Invoice #: INV-{sale['sale_id']}")
        p.drawString(400, height - 115, f"Date: {sale['sale_date']}")

        p.setStrokeColor(colors.lightgrey)
        p.line(50, height - 140, 550, height - 140)

        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, height - 170, "BILL TO:")
        p.setFont("Helvetica", 11)
        p.drawString(50, height - 190, sale['customer_name'])
        p.drawString(50, height - 205, sale['customer_email'])

        p.setFillColor(colors.HexColor("#f0f4ff"))
        p.rect(50, height - 260, 500, 30, fill=1, stroke=0)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 11)
        p.drawString(60, height - 250, "DESCRIPTION")
        p.drawString(300, height - 250, "QTY")
        p.drawString(370, height - 250, "UNIT PRICE")
        p.drawString(470, height - 250, "TOTAL")

        p.setFont("Helvetica", 11)
        p.drawString(60, height - 290, sale['product_name'])
        p.drawString(300, height - 290, str(sale['quantity']))
        p.drawString(370, height - 290, indian_currency(sale['unit_price']))
        p.drawString(470, height - 290, indian_currency(sale['total_amount']))

        p.line(50, height - 320, 550, height - 320)
        p.setFont("Helvetica-Bold", 12)
        p.drawString(350, height - 350, "GRAND TOTAL:")
        p.drawString(470, height - 350, indian_currency(sale['total_amount']))

        p.setFont("Helvetica-Oblique", 10)
        p.setFillColor(colors.grey)
        p.drawCentredString(width / 2, 50, "Thank you for your business! This is a system-generated invoice.")

        p.showPage()
        p.save()
        buffer.seek(0)
        return send_file(buffer, as_attachment=True,
                         download_name=f"Invoice_INV-{sale_id}.pdf",
                         mimetype='application/pdf')
    except Exception as e:
        return f"Error: {str(e)}", 500


@reports_bp.route('/report/payslip/<int:payroll_id>')
def generate_payslip(payroll_id):
    if 'user_id' not in session:
        abort(401)

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT pr.*, u.name as emp_name, u.email as emp_email,
                       e.job_title, e.emp_id, e.department, e.phone
                FROM payroll pr
                JOIN employee e ON pr.emp_id = e.emp_id
                JOIN users u ON e.user_id = u.user_id
                WHERE pr.payroll_id = %s
            """, (payroll_id,))
            pay = cursor.fetchone()

            cursor.execute("SELECT * FROM company_settings LIMIT 1")
            company = cursor.fetchone()

        if not pay:
            return "Pay Slip not found", 404

        company_name = company.get('company_name', 'Nexus ERP') if company else 'Nexus ERP'
        company_addr = company.get('address', 'India') if company else 'India'

        total_ctc = float(pay['basic'])
        total_deductions = float(pay['deductions'])
        net_pay = float(pay['net_pay'])

        basic = round(total_ctc * 0.50)
        hra = round(basic * 0.40)
        conveyance = 1600
        education = 300
        special = max(0, round(total_ctc - basic - hra - conveyance - education))
        gross_earnings = total_ctc

        month_name = datetime.date(1900, pay['month'], 1).strftime('%B')
        pay_date = datetime.date(pay['year'], pay['month'], 28).strftime('%d/%m/%Y')
        join_date = "N/A"

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        y = height - 40

        blue = colors.HexColor("#3b82f6")
        dark = colors.HexColor("#1e293b")
        grey_bg = colors.HexColor("#f1f5f9")
        green_bg = colors.HexColor("#ecfdf5")
        green_border = colors.HexColor("#10b981")
        light_blue = colors.HexColor("#eff6ff")

        # Header bar
        c.setFillColor(blue)
        c.rect(0, y - 20, width, 50, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(40, y - 5, company_name.upper())
        c.setFont("Helvetica", 10)
        c.drawString(40, y + 10, company_addr)

        c.setFont("Helvetica-Bold", 14)
        c.drawRightString(width - 40, y + 10, f"Payslip For the Month")
        c.setFont("Helvetica-Bold", 16)
        c.drawRightString(width - 40, y - 8, f"{month_name} {pay['year']}")

        y -= 50

        # Separator
        c.setStrokeColor(colors.HexColor("#e2e8f0"))
        c.setLineWidth(1)
        c.line(40, y, width - 40, y)
        y -= 25

        # EMPLOYEE SUMMARY section
        c.setFillColor(dark)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, "EMPLOYEE SUMMARY")
        y -= 5

        info_x = 40
        val_x = 180
        line_h = 20

        fields = [
            ("Employee Name", pay['emp_name']),
            ("Designation", pay['job_title'] or "N/A"),
            ("Employee ID", str(pay['emp_id'])),
            ("Department", str(pay.get('department', 'N/A') or 'N/A')),
            ("Pay Period", f"{month_name} {pay['year']}"),
            ("Pay Date", pay_date),
        ]

        # Draw info on left
        for i, (label, value) in enumerate(fields):
            fy = y - (i * line_h)
            c.setFont("Helvetica-Bold", 9)
            c.setFillColor(colors.HexColor("#64748b"))
            c.drawString(info_x, fy, label)
            c.setFont("Helvetica", 9)
            c.setFillColor(dark)
            c.drawString(val_x, fy, f":  {value}")

        # Net Pay box on right
        box_x = 340
        box_y = y + 10
        box_w = 210
        box_h = 110

        c.setStrokeColor(green_border)
        c.setLineWidth(1.5)
        c.setFillColor(green_bg)
        c.roundRect(box_x, box_y - box_h + 10, box_w, box_h, 8, fill=1, stroke=1)

        c.setFillColor(colors.HexColor("#059669"))
        c.setFont("Helvetica-Bold", 28)
        c.drawCentredString(box_x + box_w / 2, box_y - 25, indian_currency(net_pay))

        c.setFillColor(colors.HexColor("#374151"))
        c.setFont("Helvetica", 10)
        c.drawCentredString(box_x + box_w / 2, box_y - 45, "Employee Net Pay")

        c.setStrokeColor(colors.HexColor("#d1d5db"))
        c.setLineWidth(0.5)
        c.line(box_x + 15, box_y - 55, box_x + box_w - 15, box_y - 55)

        c.setFont("Helvetica", 9)
        c.setFillColor(dark)
        c.drawString(box_x + 20, box_y - 72, "Paid Days")
        c.drawString(box_x + 20, box_y - 88, "LOP Days")
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(box_x + box_w - 20, box_y - 72, ":  30")
        c.drawRightString(box_x + box_w - 20, box_y - 88, ":  0")

        y -= 140

        # Separator
        c.setStrokeColor(colors.HexColor("#e2e8f0"))
        c.line(40, y, width - 40, y)
        y -= 25

        # EARNINGS & DEDUCTIONS Table
        col_left = 40
        col_mid = 310
        ear_amt_x = 210
        ear_ytd_x = 260
        ded_amt_x = 480
        ded_ytd_x = 530

        # Table Header
        c.setFillColor(grey_bg)
        c.rect(col_left, y - 22, (width - 80) / 2, 22, fill=1, stroke=0)
        c.rect(col_mid, y - 22, (width - 80) / 2, 22, fill=1, stroke=0)

        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(dark)
        c.drawString(col_left + 10, y - 15, "EARNINGS")
        c.drawString(ear_amt_x, y - 15, "AMOUNT")
        c.drawString(ear_ytd_x, y - 15, "YTD")
        c.drawString(col_mid + 10, y - 15, "DEDUCTIONS")
        c.drawString(ded_amt_x, y - 15, "AMOUNT")
        c.drawString(ded_ytd_x, y - 15, "YTD")

        y -= 22

        earnings = [
            ("Basic", basic, basic * 3),
            ("House Rent Allowance", hra, hra * 3),
            ("Conveyance Allowance", conveyance, conveyance * 3),
            ("Children Education Allowance", education, education * 3),
            ("Special Allowance", special, special * 3),
        ]

        deductions = [
            ("EPF Contribution", 0, 0),
            ("Professional Tax", 0, 0),
        ]

        max_rows = max(len(earnings), len(deductions))
        row_h = 22

        for i in range(max_rows):
            fy = y - (i * row_h)

            if i % 2 == 0:
                c.setFillColor(colors.HexColor("#f8fafc"))
                c.rect(col_left, fy - row_h + 5, (width - 80) / 2, row_h, fill=1, stroke=0)
                c.rect(col_mid, fy - row_h + 5, (width - 80) / 2, row_h, fill=1, stroke=0)

            if i < len(earnings):
                c.setFont("Helvetica", 9)
                c.setFillColor(dark)
                c.drawString(col_left + 10, fy - 10, earnings[i][0])
                c.setFont("Helvetica-Bold", 9)
                c.drawString(ear_amt_x, fy - 10, indian_currency(earnings[i][1]))
                c.setFont("Helvetica", 9)
                c.setFillColor(colors.HexColor("#64748b"))
                c.drawString(ear_ytd_x, fy - 10, indian_currency(earnings[i][2]))

            if i < len(deductions):
                c.setFont("Helvetica", 9)
                c.setFillColor(dark)
                c.drawString(col_mid + 10, fy - 10, deductions[i][0])
                c.setFont("Helvetica-Bold", 9)
                c.drawString(ded_amt_x, fy - 10, indian_currency(deductions[i][1]))
                c.setFont("Helvetica", 9)
                c.setFillColor(colors.HexColor("#64748b"))
                c.drawString(ded_ytd_x, fy - 10, indian_currency(deductions[i][2]))

        y -= max_rows * row_h

        # Totals row
        c.setStrokeColor(colors.HexColor("#cbd5e1"))
        c.setLineWidth(0.5)
        c.line(col_left, y, col_left + (width - 80) / 2, y)
        c.line(col_mid, y, col_mid + (width - 80) / 2, y)
        y -= 20

        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(dark)
        c.drawString(col_left + 10, y, "Gross Earnings")
        c.drawString(ear_amt_x, y, indian_currency(gross_earnings))
        c.drawString(col_mid + 10, y, "Total Deductions")
        c.drawString(ded_amt_x, y, indian_currency(total_deductions))

        y -= 35

        # TOTAL NET PAYABLE box
        c.setStrokeColor(green_border)
        c.setLineWidth(1.5)
        c.setFillColor(green_bg)
        c.roundRect(col_left, y - 30, width - 80, 40, 6, fill=1, stroke=1)

        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(dark)
        c.drawString(col_left + 15, y - 5, "TOTAL NET PAYABLE")
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.HexColor("#64748b"))
        c.drawString(col_left + 15, y - 20, "Gross Earnings - Total Deductions")

        c.setFont("Helvetica-Bold", 16)
        c.setFillColor(green_border)
        c.drawRightString(col_left + width - 80 - 15, y - 10, indian_currency(net_pay))

        y -= 55

        # Amount in words
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.HexColor("#64748b"))
        words = amount_in_words(net_pay)
        c.drawString(col_left, y, f"Amount In Words : {words}")

        y -= 30

        # Footer separator
        c.setStrokeColor(colors.HexColor("#e2e8f0"))
        c.line(40, y, width - 40, y)
        y -= 15

        # Footer
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(colors.HexColor("#94a3b8"))
        c.drawCentredString(width / 2, y,
            "-- This document has been automatically generated by Nexus ERP; therefore, a signature is not required. --")

        c.showPage()
        c.save()
        buffer.seek(0)

        safe_name = re.sub(r'[^\w\-_]', '_', pay['emp_name'])
        return send_file(buffer, as_attachment=True,
                         download_name=f"Payslip_{safe_name}_{pay['month']}_{pay['year']}.pdf",
                         mimetype='application/pdf')

    except Exception as e:
        return f"Error: {str(e)}", 500
