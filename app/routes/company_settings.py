from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.db import get_db_connection
from app.utils import admin_required

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/company-settings')
@admin_required
def company_settings():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

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
        flash(f'Error loading company settings: {str(e)}', 'danger')
        return redirect(url_for('dashboard.dashboard'))

@settings_bp.route('/company-settings/update', methods=['POST'])
@admin_required
def update_company_settings():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

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
                UPDATE company_settings
                SET company_name=%s, address=%s, phone=%s, email=%s, tax_rate=%s, currency=%s
                WHERE id = 1
            """, (company_name, address, phone, email, tax_rate, currency))
        conn.commit()
        conn.close()
        flash('Company settings updated successfully.', 'success')
    except Exception as e:
        flash(f'Error updating company settings: {str(e)}', 'danger')

    return redirect(url_for('settings.company_settings'))
