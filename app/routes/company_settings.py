from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.db import get_db_connection
from app.utils import admin_required
import logging

settings_bp = Blueprint('settings', __name__)

logger = logging.getLogger(__name__)


@settings_bp.route('/company-settings')
@admin_required
def company_settings():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM company_settings WHERE id = 1")
            settings = cursor.fetchone()
        conn.close()

        if not settings:
            settings = {
                'company_name': '',
                'address': '',
                'phone': '',
                'email': '',
                'tax_rate': 0,
                'currency': 'INR'
            }

        return render_template('company_settings.html', settings=settings)
    except Exception as e:
        logger.error("Company settings error: %s", e)
        flash('An unexpected error occurred.', 'danger')
        return redirect(url_for('dashboard.dashboard'))


@settings_bp.route('/company-settings/update', methods=['POST'])
@admin_required
def update_company_settings():
    company_name = request.form.get('company_name')
    address = request.form.get('address')
    phone = request.form.get('phone')
    email = request.form.get('email')
    tax_rate = request.form.get('tax_rate')
    currency = request.form.get('currency')

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO company_settings (id, company_name, address, phone, email, tax_rate, currency)
                VALUES (1, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    company_name = EXCLUDED.company_name,
                    address = EXCLUDED.address,
                    phone = EXCLUDED.phone,
                    email = EXCLUDED.email,
                    tax_rate = EXCLUDED.tax_rate,
                    currency = EXCLUDED.currency
            """, (company_name, address, phone, email, tax_rate, currency))
        conn.commit()
        conn.close()
        flash('Company settings updated successfully.', 'success')
    except Exception as e:
        logger.error("Update company settings error: %s", e)
        flash('An unexpected error occurred.', 'danger')

    return redirect(url_for('settings.company_settings'))
