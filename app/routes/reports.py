from flask import Blueprint, send_file, session, abort
import pymysql
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from io import BytesIO
import datetime

reports_bp = Blueprint('reports', __name__)

from app.db import get_db_connection

@reports_bp.route('/report/invoice/<int:sale_id>')
def generate_invoice(sale_id):
    if 'user_id' not in session:
        abort(401)
        
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Fetch sale details
            cursor.execute("""
                SELECT s.*, c.name as customer_name, c.email as customer_email, p.name as product_name, p.unit_price 
                FROM sale s 
                JOIN customer c ON s.customer_id = c.customer_id 
                JOIN product p ON s.product_id = p.product_id 
                WHERE s.sale_id = %s
            """, (sale_id,))
            sale = cursor.fetchone()
            
        if not sale:
            return "Invoice not found", 404
            
        # Create PDF
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Header
        p.setFont("Helvetica-Bold", 24)
        p.setFillColor(colors.HexColor("#3b82f6"))
        p.drawString(50, height - 80, "NEXUS ERP")
        
        p.setFont("Helvetica", 10)
        p.setFillColor(colors.black)
        p.drawString(50, height - 100, "123 Business Avenue, Tech City")
        p.drawString(50, height - 115, "Contact: +1 234 567 890")
        
        p.setFont("Helvetica-Bold", 16)
        p.drawString(400, height - 80, "INVOICE")
        p.setFont("Helvetica", 10)
        p.drawString(400, height - 100, f"Invoice #: INV-{sale['sale_id']}")
        p.drawString(400, height - 115, f"Date: {sale['sale_date']}")
        
        # Horizontal Line
        p.setStrokeColor(colors.lightgrey)
        p.line(50, height - 140, 550, height - 140)
        
        # Bill To
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, height - 170, "BILL TO:")
        p.setFont("Helvetica", 11)
        p.drawString(50, height - 190, sale['customer_name'])
        p.drawString(50, height - 205, sale['customer_email'])
        
        # Table Header
        p.setFillColor(colors.HexColor("#f8fafc"))
        p.rect(50, height - 260, 500, 30, fill=1, stroke=0)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 11)
        p.drawString(60, height - 250, "DESCRIPTION")
        p.drawString(300, height - 250, "QTY")
        p.drawString(380, height - 250, "UNIT PRICE")
        p.drawString(480, height - 250, "TOTAL")
        
        # Table Row
        p.setFont("Helvetica", 11)
        p.drawString(60, height - 290, sale['product_name'])
        p.drawString(300, height - 290, str(sale['quantity']))
        p.drawString(380, height - 290, f"${sale['unit_price']:.2f}")
        p.drawString(480, height - 290, f"${sale['total_amount']:.2f}")
        
        # Totals
        p.line(50, height - 320, 550, height - 320)
        p.setFont("Helvetica-Bold", 12)
        p.drawString(380, height - 350, "GRAND TOTAL:")
        p.drawString(480, height - 350, f"${sale['total_amount']:.2f}")
        
        # Footer
        p.setFont("Helvetica-Oblique", 10)
        p.setFillColor(colors.grey)
        p.drawCentredString(width / 2, 50, "Thank you for your business! This is a system-generated invoice.")
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"Invoice_INV-{sale_id}.pdf", mimetype='application/pdf')
        
    except Exception as e:
        return f"Error: {str(e)}", 500

@reports_bp.route('/report/payslip/<int:payroll_id>')
def generate_payslip(payroll_id):
    if 'user_id' not in session:
        abort(401)
        
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Fetch payroll details
            cursor.execute("""
                SELECT pr.*, u.name as emp_name, u.email as emp_email, e.job_title 
                FROM payroll pr 
                JOIN employee e ON pr.emp_id = e.emp_id 
                JOIN users u ON e.user_id = u.user_id 
                WHERE pr.payroll_id = %s
            """, (payroll_id,))
            pay = cursor.fetchone()
            
        if not pay:
            return "Pay Slip not found", 404
            
        # Create PDF
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Header
        p.setFont("Helvetica-Bold", 20)
        p.drawString(50, height - 80, "Nexus ERP - Salary Slip")
        p.setFont("Helvetica", 10)
        p.drawString(50, height - 100, f"Period: {pay['month']} {pay['year']}")
        
        # Employee Info
        p.rect(50, height - 200, 500, 80)
        p.setFont("Helvetica-Bold", 11)
        p.drawString(60, height - 140, "Employee Name:")
        p.drawString(60, height - 160, "Designation:")
        p.drawString(60, height - 180, "Email:")
        
        p.setFont("Helvetica", 11)
        p.drawString(180, height - 140, pay['emp_name'])
        p.drawString(180, height - 160, pay['job_title'])
        p.drawString(180, height - 180, pay['emp_email'])
        
        # Earnings Table
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, height - 240, "EARNINGS")
        p.rect(50, height - 350, 500, 100)
        p.line(50, height - 270, 550, height - 270)
        
        p.setFont("Helvetica", 11)
        p.drawString(60, height - 290, "Basic Salary")
        p.drawString(450, height - 290, f"${pay['basic']:.2f}")
        
        p.drawString(60, height - 310, "Allowances / Bonuses")
        p.drawString(450, height - 310, "$0.00")
        
        # Deductions
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, height - 380, "DEDUCTIONS")
        p.rect(50, height - 450, 500, 50)
        p.setFont("Helvetica", 11)
        p.drawString(60, height - 420, "Tax / Other Deductions")
        p.drawString(450, height - 420, "$0.00")
        
        # Net Pay
        p.setFillColor(colors.HexColor("#eef2ff"))
        p.rect(50, height - 520, 500, 40, fill=1)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(60, height - 505, "NET SALARY PAYABLE:")
        p.drawString(430, height - 505, f"${pay['net_pay']:.2f}")
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"PaySlip_{pay['emp_name']}_{pay['month']}.pdf", mimetype='application/pdf')
        
    except Exception as e:
        return f"Error: {str(e)}", 500
