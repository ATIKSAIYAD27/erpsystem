import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def get_email_config():
    return {
        'server': os.environ.get('SMTP_SERVER', 'smtp.gmail.com'),
        'port': int(os.environ.get('SMTP_PORT', 587)),
        'username': os.environ.get('SMTP_USERNAME', ''),
        'password': os.environ.get('SMTP_PASSWORD', ''),
        'from_name': os.environ.get('SMTP_FROM_NAME', 'Nexus ERP'),
        'from_email': os.environ.get('SMTP_FROM_EMAIL', ''),
        'use_tls': os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true',
    }


def send_email(to_email, subject, html_body, attachments=None):
    config = get_email_config()
    if not config['username'] or not config['password']:
        logger.warning("SMTP not configured. Email not sent to %s", to_email)
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = f"{config['from_name']} <{config['from_email'] or config['username']}>"
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(html_body, 'html'))

        if attachments:
            for filepath, filename in attachments:
                if os.path.exists(filepath):
                    with open(filepath, 'rb') as f:
                        attachment = MIMEApplication(f.read())
                        attachment.add_header('Content-Disposition', 'attachment', filename=filename)
                        msg.attach(attachment)

        server = smtplib.SMTP(config['server'], config['port'])
        if config['use_tls']:
            server.starttls()
        server.login(config['username'], config['password'])
        server.send_message(msg)
        server.quit()
        logger.info("Email sent to %s: %s", to_email, subject)
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)
        return False


def send_quotation_email(to_email, customer_name, quote_number, grand_total, pdf_path=None):
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #3b82f6, #8b5cf6); padding: 30px; text-align: center;">
            <h1 style="color: white; margin: 0;">Nexus ERP</h1>
        </div>
        <div style="padding: 30px; background: #f8fafc;">
            <h2 style="color: #1e293b;">Quotation {quote_number}</h2>
            <p style="color: #64748b;">Dear {customer_name},</p>
            <p style="color: #64748b;">Please find attached your quotation for your review.</p>
            <div style="background: white; border-radius: 12px; padding: 20px; margin: 20px 0; border: 1px solid #e2e8f0;">
                <p style="color: #64748b; margin: 0;">Quotation Total</p>
                <p style="color: #10b981; font-size: 28px; font-weight: bold; margin: 5px 0;">Rs. {grand_total:,.2f}</p>
            </div>
            <p style="color: #64748b;">Please review the attached quotation and let us know if you have any questions.</p>
            <p style="color: #64748b;">Best regards,<br><strong>Nexus ERP Team</strong></p>
        </div>
        <div style="text-align: center; padding: 15px; color: #94a3b8; font-size: 12px;">
            This is an automated email from Nexus ERP
        </div>
    </div>
    """
    attachments = [(pdf_path, f"{quote_number}.pdf")] if pdf_path and os.path.exists(pdf_path) else None
    return send_email(to_email, f"Quotation {quote_number} - Nexus ERP", html, attachments)


def send_leave_notification(to_email, employee_name, leave_type, status, dates):
    color = '#10b981' if status == 'Approved' else '#ef4444' if status == 'Rejected' else '#f59e0b'
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #3b82f6, #8b5cf6); padding: 30px; text-align: center;">
            <h1 style="color: white; margin: 0;">Nexus ERP</h1>
        </div>
        <div style="padding: 30px; background: #f8fafc;">
            <h2 style="color: #1e293b;">Leave {status}</h2>
            <div style="background: white; border-radius: 12px; padding: 20px; margin: 20px 0; border-left: 4px solid {color};">
                <p style="margin: 5px 0;"><strong>Employee:</strong> {employee_name}</p>
                <p style="margin: 5px 0;"><strong>Type:</strong> {leave_type}</p>
                <p style="margin: 5px 0;"><strong>Dates:</strong> {dates}</p>
                <p style="margin: 5px 0; color: {color}; font-weight: bold;">Status: {status}</p>
            </div>
        </div>
    </div>
    """
    return send_email(to_email, f"Leave {status} - Nexus ERP", html)


def send_payroll_notification(to_email, employee_name, month, year, net_pay):
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #3b82f6, #8b5cf6); padding: 30px; text-align: center;">
            <h1 style="color: white; margin: 0;">Nexus ERP</h1>
        </div>
        <div style="padding: 30px; background: #f8fafc;">
            <h2 style="color: #1e293b;">Payslip Generated</h2>
            <p style="color: #64748b;">Dear {employee_name},</p>
            <p style="color: #64748b;">Your payslip for <strong>{month}/{year}</strong> has been generated.</p>
            <div style="background: white; border-radius: 12px; padding: 20px; margin: 20px 0; border: 1px solid #e2e8f0; text-align: center;">
                <p style="color: #64748b; margin: 0;">Net Pay</p>
                <p style="color: #10b981; font-size: 28px; font-weight: bold; margin: 5px 0;">Rs. {net_pay:,.2f}</p>
            </div>
            <p style="color: #64748b;">Please check your dashboard for the detailed payslip.</p>
        </div>
    </div>
    """
    return send_email(to_email, f"Payslip {month}/{year} - Nexus ERP", html)


def send_welcome_email(to_email, name):
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #3b82f6, #8b5cf6); padding: 30px; text-align: center;">
            <h1 style="color: white; margin: 0;">Welcome to Nexus ERP</h1>
        </div>
        <div style="padding: 30px; background: #f8fafc;">
            <h2 style="color: #1e293b;">Hello {name}!</h2>
            <p style="color: #64748b;">Your account has been created successfully. You can now log in to access the system.</p>
            <div style="text-align: center; margin: 20px 0;">
                <a href="#" style="background: linear-gradient(135deg, #3b82f6, #8b5cf6); color: white; padding: 14px 30px; border-radius: 12px; text-decoration: none; font-weight: bold;">Login to Nexus ERP</a>
            </div>
        </div>
    </div>
    """
    return send_email(to_email, "Welcome to Nexus ERP", html)
