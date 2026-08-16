from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file, jsonify, abort
from datetime import datetime, timedelta
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from io import BytesIO
import logging
import re

from app.utils import login_required, manager_or_admin_required, admin_required, log_audit, indian_currency, get_db, safe_int, safe_float, amount_in_words

quotation_bp = Blueprint('quotation', __name__)
logger = logging.getLogger(__name__)

VALID_STATUSES = ['Draft', 'Sent', 'Accepted', 'Rejected', 'Expired']


@quotation_bp.route('/quotations')
@login_required
def quotation_list():
    status_filter = request.args.get('status', '')
    search_query = request.args.get('q', '')

    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                base_sql = """
                    SELECT q.*, c.name as customer_name, c.email as customer_email,
                           u.name as created_by_name,
                           (SELECT COUNT(*) FROM quotation_item qi WHERE qi.quote_id = q.quote_id) as item_count
                    FROM quotation q
                    LEFT JOIN customer c ON q.customer_id = c.customer_id
                    LEFT JOIN users u ON q.created_by = u.user_id
                    WHERE 1=1
                """
                params = []

                if status_filter:
                    base_sql += " AND q.status = %s"
                    params.append(status_filter)

                if search_query:
                    base_sql += " AND (q.quote_number LIKE %s OR c.name LIKE %s OR q.subject LIKE %s)"
                    params.extend([f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'])

                base_sql += " ORDER BY q.created_at DESC"

                cursor.execute(base_sql, params)
                quotations = cursor.fetchall()

                cursor.execute("SELECT customer_id, name FROM customer ORDER BY name")
                customers = cursor.fetchall()

                cursor.execute("SELECT COUNT(*) as total FROM quotation")
                total_quotes = cursor.fetchone()['total']

                cursor.execute("SELECT COUNT(*) as total FROM quotation WHERE status = 'Accepted'")
                accepted = cursor.fetchone()['total']

                cursor.execute("SELECT COUNT(*) as total FROM quotation WHERE status = 'Sent'")
                pending = cursor.fetchone()['total']

                cursor.execute("SELECT SUM(grand_total) as total FROM quotation WHERE status = 'Accepted'")
                total_value = float(cursor.fetchone()['total'] or 0)

        for q in quotations:
            if q.get('created_at'):
                q['created_at'] = q['created_at'].strftime('%d/%m/%Y %H:%M')
            if q.get('valid_until'):
                q['valid_until'] = q['valid_until'].strftime('%d/%m/%Y')

        return render_template('quotations.html',
                               quotations=quotations,
                               customers=customers,
                               total_quotes=total_quotes,
                               accepted=accepted,
                               pending=pending,
                               total_value=total_value,
                               status_filter=status_filter,
                               search_query=search_query)
    except Exception as e:
        logger.error("Quotation list error: %s", e)
        flash('An error occurred.', 'danger')
        return render_template('quotations.html', quotations=[], customers=[],
                               total_quotes=0, accepted=0, pending=0, total_value=0)


@quotation_bp.route('/quotations/create', methods=['GET', 'POST'])
@login_required
def quotation_create():
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        subject = request.form.get('subject', '').strip()
        notes = request.form.get('notes', '').strip()
        terms = request.form.get('terms', '').strip()
        discount_pct = safe_float(request.form.get('discount_pct', 0) or 0)
        tax_pct = safe_float(request.form.get('tax_pct', 0) or 0)
        valid_days = safe_int(request.form.get('valid_days', 30) or 30)

        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        discounts = request.form.getlist('discount[]')

        if not customer_id or not subject:
            flash('Customer and subject are required.', 'danger')
            return redirect(url_for('quotation.quotation_create'))

        if not product_ids:
            flash('At least one item is required.', 'danger')
            return redirect(url_for('quotation.quotation_create'))

        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT MAX(quote_number) as last_num FROM quotation")
                    row = cursor.fetchone()
                    last_num = row['last_num'] if row and row['last_num'] else 'QUO-0000'
                    num_part = safe_int(last_num.split('-')[1]) + 1
                    quote_number = f"QUO-{num_part:04d}"

                    today = datetime.now().date()
                    valid_until = today + timedelta(days=valid_days)

                    subtotal = 0
                    items_data = []
                    for i in range(len(product_ids)):
                        qty = safe_int(quantities[i])
                        price = safe_float(unit_prices[i])
                        disc = safe_float(discounts[i]) if i < len(discounts) else 0
                        line_total = (price * qty) - disc
                        subtotal += line_total
                        items_data.append((product_ids[i], qty, price, disc, line_total))

                    discount_amount = subtotal * (discount_pct / 100)
                    after_discount = subtotal - discount_amount
                    tax_amount = after_discount * (tax_pct / 100)
                    grand_total = after_discount + tax_amount

                    cursor.execute("""
                        INSERT INTO quotation (quote_number, customer_id, subject, notes, terms,
                            subtotal, discount_pct, discount_amount, tax_pct, tax_amount,
                            grand_total, valid_until, status, created_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Draft', %s)
                    """, (quote_number, customer_id, subject, notes, terms,
                          subtotal, discount_pct, discount_amount, tax_pct, tax_amount,
                          grand_total, valid_until, session['user_id']))
                    quote_id = cursor.lastrowid

                    for product_id, qty, price, disc, line_total in items_data:
                        cursor.execute("""
                            INSERT INTO quotation_item (quote_id, product_id, quantity, unit_price, discount, line_total)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (quote_id, product_id, qty, price, disc, line_total))

                conn.commit()
            log_audit(session['user_id'], f"Created quotation {quote_number}")
            flash(f'Quotation {quote_number} created successfully!', 'success')
            return redirect(url_for('quotation.quotation_detail', quote_id=quote_id))

        except Exception as e:
            logger.error("Create quotation error: %s", e)
            flash('An error occurred.', 'danger')

        return redirect(url_for('quotation.quotation_list'))

    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT customer_id, name FROM customer ORDER BY name")
                customers = cursor.fetchall()
                cursor.execute("SELECT product_id, name, unit_price, quantity as stock FROM product WHERE quantity > 0 ORDER BY name")
                products = cursor.fetchall()
        return render_template('quotation_form.html', customers=customers, products=products, quotation=None)
    except Exception as e:
        logger.error("Quotation form error: %s", e)
        flash('An error occurred.', 'danger')
        return redirect(url_for('quotation.quotation_list'))


@quotation_bp.route('/quotations/<int:quote_id>')
@login_required
def quotation_detail(quote_id):
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT q.*, c.name as customer_name, c.email as customer_email,
                           c.phone as customer_phone, c.address as customer_address,
                           u.name as created_by_name
                    FROM quotation q
                    LEFT JOIN customer c ON q.customer_id = c.customer_id
                    LEFT JOIN users u ON q.created_by = u.user_id
                    WHERE q.quote_id = %s
                """, (quote_id,))
                quotation = cursor.fetchone()

                if not quotation:
                    flash('Quotation not found.', 'danger')
                    return redirect(url_for('quotation.quotation_list'))

                cursor.execute("""
                    SELECT qi.*, p.name as product_name, p.sku
                    FROM quotation_item qi
                    LEFT JOIN product p ON qi.product_id = p.product_id
                    WHERE qi.quote_id = %s
                """, (quote_id,))
                items = cursor.fetchall()

                cursor.execute("SELECT * FROM company_settings LIMIT 1")
                company = cursor.fetchone()

        if quotation.get('valid_until'):
            quotation['valid_until'] = quotation['valid_until'].strftime('%d/%m/%Y')
        if quotation.get('created_at'):
            quotation['created_at'] = quotation['created_at'].strftime('%d/%m/%Y %H:%M')

        return render_template('quotation_detail.html',
                               quotation=quotation, items=items, company=company)
    except Exception as e:
        logger.error("Quotation detail error: %s", e)
        flash('An error occurred.', 'danger')
        return redirect(url_for('quotation.quotation_list'))


@quotation_bp.route('/quotations/<int:quote_id>/edit', methods=['GET', 'POST'])
@login_required
def quotation_edit(quote_id):
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        notes = request.form.get('notes', '').strip()
        terms = request.form.get('terms', '').strip()
        discount_pct = safe_float(request.form.get('discount_pct', 0) or 0)
        tax_pct = safe_float(request.form.get('tax_pct', 0) or 0)
        valid_days = safe_int(request.form.get('valid_days', 30) or 30)

        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        discounts = request.form.getlist('discount[]')

        if not subject:
            flash('Subject is required.', 'danger')
            return redirect(url_for('quotation.quotation_edit', quote_id=quote_id))

        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT status FROM quotation WHERE quote_id = %s", (quote_id,))
                    q = cursor.fetchone()
                    if not q:
                        flash('Quotation not found.', 'danger')
                        return redirect(url_for('quotation.quotation_list'))
                    if q['status'] not in ('Draft', 'Sent'):
                        flash('Only Draft or Sent quotations can be edited.', 'danger')
                        return redirect(url_for('quotation.quotation_detail', quote_id=quote_id))

                    cursor.execute("DELETE FROM quotation_item WHERE quote_id = %s", (quote_id,))

                    subtotal = 0
                    items_data = []
                    for i in range(len(product_ids)):
                        qty = safe_int(quantities[i])
                        price = safe_float(unit_prices[i])
                        disc = safe_float(discounts[i]) if i < len(discounts) else 0
                        line_total = (price * qty) - disc
                        subtotal += line_total
                        items_data.append((product_ids[i], qty, price, disc, line_total))

                    discount_amount = subtotal * (discount_pct / 100)
                    after_discount = subtotal - discount_amount
                    tax_amount = after_discount * (tax_pct / 100)
                    grand_total = after_discount + tax_amount

                    valid_until = datetime.now().date() + timedelta(days=valid_days)

                    cursor.execute("""
                        UPDATE quotation SET subject=%s, notes=%s, terms=%s,
                            subtotal=%s, discount_pct=%s, discount_amount=%s,
                            tax_pct=%s, tax_amount=%s, grand_total=%s, valid_until=%s
                        WHERE quote_id=%s
                    """, (subject, notes, terms, subtotal, discount_pct, discount_amount,
                          tax_pct, tax_amount, grand_total, valid_until, quote_id))

                    for product_id, qty, price, disc, line_total in items_data:
                        cursor.execute("""
                            INSERT INTO quotation_item (quote_id, product_id, quantity, unit_price, discount, line_total)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (quote_id, product_id, qty, price, disc, line_total))

                conn.commit()
            log_audit(session['user_id'], f"Edited quotation QUO-{quote_id:04d}")
            flash('Quotation updated successfully!', 'success')
            return redirect(url_for('quotation.quotation_detail', quote_id=quote_id))

        except Exception as e:
            logger.error("Edit quotation error: %s", e)
            flash('An error occurred.', 'danger')

        return redirect(url_for('quotation.quotation_detail', quote_id=quote_id))

    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM quotation WHERE quote_id = %s", (quote_id,))
                quotation = cursor.fetchone()
                if not quotation:
                    flash('Quotation not found.', 'danger')
                    return redirect(url_for('quotation.quotation_list'))

                cursor.execute("""
                    SELECT qi.*, p.name as product_name
                    FROM quotation_item qi
                    LEFT JOIN product p ON qi.product_id = p.product_id
                    WHERE qi.quote_id = %s
                """, (quote_id,))
                items = cursor.fetchall()

                cursor.execute("SELECT customer_id, name FROM customer ORDER BY name")
                customers = cursor.fetchall()
                cursor.execute("SELECT product_id, name, unit_price, quantity as stock FROM product WHERE quantity > 0 ORDER BY name")
                products = cursor.fetchall()

        if quotation.get('valid_until'):
            diff = (quotation['valid_until'] - datetime.now().date()).days
            quotation['valid_days'] = max(diff, 1)

        return render_template('quotation_form.html',
                               quotation=quotation, items=items, customers=customers, products=products)
    except Exception as e:
        logger.error("Edit quotation form error: %s", e)
        flash('An error occurred.', 'danger')
        return redirect(url_for('quotation.quotation_list'))


@quotation_bp.route('/quotations/<int:quote_id>/status', methods=['POST'])
@login_required
def quotation_status(quote_id):
    new_status = request.form.get('status')
    if new_status not in VALID_STATUSES:
        flash('Invalid status.', 'danger')
        return redirect(url_for('quotation.quotation_detail', quote_id=quote_id))

    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE quotation SET status = %s WHERE quote_id = %s", (new_status, quote_id))
            conn.commit()
        log_audit(session['user_id'], f"Changed quotation QUO-{quote_id:04d} status to {new_status}")
        flash(f'Quotation marked as {new_status}.', 'success')
    except Exception as e:
        logger.error("Update quotation status error: %s", e)
        flash('An error occurred.', 'danger')

    return redirect(url_for('quotation.quotation_detail', quote_id=quote_id))


@quotation_bp.route('/quotations/<int:quote_id>/convert-to-sale', methods=['POST'])
@login_required
def convert_to_sale(quote_id):
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM quotation WHERE quote_id = %s", (quote_id,))
                quotation = cursor.fetchone()

                if not quotation:
                    flash('Quotation not found.', 'danger')
                    return redirect(url_for('quotation.quotation_list'))

                if quotation['status'] != 'Accepted':
                    flash('Only accepted quotations can be converted to sales.', 'danger')
                    return redirect(url_for('quotation.quotation_detail', quote_id=quote_id))

                cursor.execute("""
                    SELECT qi.*, p.name as product_name
                    FROM quotation_item qi
                    LEFT JOIN product p ON qi.product_id = p.product_id
                    WHERE qi.quote_id = %s
                """, (quote_id,))
                items = cursor.fetchall()

                sale_ids = []
                for item in items:
                    cursor.execute("SELECT quantity FROM product WHERE product_id = %s", (item['product_id'],))
                    product = cursor.fetchone()
                    if product and product['quantity'] >= item['quantity']:
                        total_amount = safe_float(item['unit_price']) * item['quantity']
                        cursor.execute("""
                            INSERT INTO sale (customer_id, product_id, quantity, total_amount, sale_date)
                            VALUES (%s, %s, %s, %s, CURDATE())
                        """, (quotation['customer_id'], item['product_id'], item['quantity'], total_amount))
                        sale_ids.append(cursor.lastrowid)

                        cursor.execute("""
                            UPDATE product SET quantity = quantity - %s WHERE product_id = %s
                        """, (item['quantity'], item['product_id']))

                cursor.execute("UPDATE quotation SET status = 'Converted' WHERE quote_id = %s", (quote_id,))

                from app.utils import notify_admin
                notify_admin(f"Quotation {quotation['quote_number']} converted to {len(sale_ids)} sale(s) worth {indian_currency(quotation['grand_total'])}", 'success')

            conn.commit()
        log_audit(session['user_id'], f"Converted quotation QUO-{quote_id:04d} to {len(sale_ids)} sale(s)")
        flash(f'Quotation converted to {len(sale_ids)} sale(s) successfully!', 'success')

    except Exception as e:
        logger.error("Convert to sale error: %s", e)
        flash('An error occurred during conversion.', 'danger')

    return redirect(url_for('quotation.quotation_detail', quote_id=quote_id))


@quotation_bp.route('/quotations/<int:quote_id>/delete', methods=['POST'])
@admin_required
def quotation_delete(quote_id):
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM quotation_item WHERE quote_id = %s", (quote_id,))
                cursor.execute("DELETE FROM quotation WHERE quote_id = %s", (quote_id,))
            conn.commit()
        log_audit(session['user_id'], f"Deleted quotation QUO-{quote_id:04d}")
        flash('Quotation deleted.', 'success')
    except Exception as e:
        logger.error("Delete quotation error: %s", e)
        flash('An error occurred.', 'danger')

    return redirect(url_for('quotation.quotation_list'))


@quotation_bp.route('/quotations/<int:quote_id>/pdf')
@login_required
def quotation_pdf(quote_id):
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT q.*, c.name as customer_name, c.email as customer_email,
                           c.phone as customer_phone, c.address as customer_address
                    FROM quotation q
                    LEFT JOIN customer c ON q.customer_id = c.customer_id
                    WHERE q.quote_id = %s
                """, (quote_id,))
                quotation = cursor.fetchone()

                if not quotation:
                    abort(404)

                cursor.execute("""
                    SELECT qi.*, p.name as product_name, p.sku
                    FROM quotation_item qi
                    LEFT JOIN product p ON qi.product_id = p.product_id
                    WHERE qi.quote_id = %s
                """, (quote_id,))
                items = cursor.fetchall()

                cursor.execute("SELECT * FROM company_settings LIMIT 1")
                company = cursor.fetchone()

        company_name = company.get('company_name', 'Nexus ERP') if company else 'Nexus ERP'
        company_addr = company.get('address', 'India') if company else 'India'
        company_phone = company.get('phone', '') if company else ''
        company_email = company.get('email', '') if company else ''

        buffer = BytesIO()
        p = pdf_canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        blue = colors.HexColor("#3b82f6")
        dark = colors.HexColor("#1e293b")
        grey = colors.HexColor("#64748b")

        p.setFillColor(blue)
        p.rect(0, height - 70, width, 70, fill=1, stroke=0)
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 22)
        p.drawString(40, height - 40, company_name.upper())
        p.setFont("Helvetica", 10)
        p.drawString(40, height - 55, f"{company_addr}  |  {company_phone}  |  {company_email}")

        p.setFillColor(dark)
        p.setFont("Helvetica-Bold", 28)
        p.drawRightString(width - 40, height - 40, "QUOTATION")
        p.setFont("Helvetica-Bold", 12)
        p.setFillColor(colors.white)
        p.drawRightString(width - 40, height - 58, quotation['quote_number'])

        p.setFont("Helvetica-Bold", 10)
        p.setFillColor(grey)
        y = height - 100
        p.drawString(40, y, "Status:")
        p.setFillColor(dark)
        p.drawString(100, y, quotation['status'])

        p.setFillColor(grey)
        p.drawString(300, y, "Date:")
        p.setFillColor(dark)
        p.drawString(350, y, quotation['created_at'].strftime('%d %B %Y') if quotation.get('created_at') else 'N/A')

        p.setFillColor(grey)
        p.drawString(400, y, "Valid Until:")
        p.setFillColor(dark)
        p.drawString(470, y, quotation['valid_until'].strftime('%d %B %Y') if quotation.get('valid_until') else 'N/A')

        y -= 30
        p.setStrokeColor(colors.HexColor("#e2e8f0"))
        p.line(40, y, width - 40, y)
        y -= 25

        p.setFont("Helvetica-Bold", 11)
        p.setFillColor(dark)
        p.drawString(40, y, "QUOTATION TO:")
        y -= 5
        p.setFont("Helvetica-Bold", 11)
        p.setFillColor(dark)
        p.drawString(40, y - 15, quotation['customer_name'] or 'N/A')
        p.setFont("Helvetica", 10)
        p.setFillColor(grey)
        if quotation.get('customer_email'):
            p.drawString(40, y - 30, quotation['customer_email'])
        if quotation.get('customer_phone'):
            p.drawString(40, y - 45, quotation['customer_phone'])
        if quotation.get('customer_address'):
            p.drawString(40, y - 60, quotation['customer_address'][:60])

        p.setFont("Helvetica-Bold", 11)
        p.setFillColor(dark)
        p.drawString(300, y - 15, "Subject:")
        p.setFont("Helvetica", 10)
        p.setFillColor(grey)
        p.drawString(370, y - 15, quotation['subject'] or 'N/A')

        y -= 85
        p.setStrokeColor(colors.HexColor("#e2e8f0"))
        p.line(40, y, width - 40, y)
        y -= 25

        table_top = y
        p.setFillColor(colors.HexColor("#f1f5f9"))
        p.rect(40, y - 22, width - 80, 22, fill=1, stroke=0)

        p.setFont("Helvetica-Bold", 9)
        p.setFillColor(dark)
        p.drawString(50, y - 15, "#")
        p.drawString(75, y - 15, "ITEM DESCRIPTION")
        p.drawString(280, y - 15, "QTY")
        p.drawString(330, y - 15, "UNIT PRICE")
        p.drawString(420, y - 15, "DISCOUNT")
        p.drawString(500, y - 15, "TOTAL")

        y -= 25
        p.setFont("Helvetica", 9)
        for idx, item in enumerate(items):
            if y < 120:
                p.showPage()
                y = height - 50

            if idx % 2 == 0:
                p.setFillColor(colors.HexColor("#f8fafc"))
                p.rect(40, y - 18, width - 80, 20, fill=1, stroke=0)

            p.setFillColor(dark)
            p.drawString(50, y - 12, str(idx + 1))
            p.drawString(75, y - 12, (item['product_name'] or 'Unknown')[:35])
            p.drawString(280, y - 12, str(item['quantity']))
            p.drawString(330, y - 12, indian_currency(item['unit_price']))
            p.drawString(420, y - 12, indian_currency(item['discount']))
            p.drawString(500, y - 12, indian_currency(item['line_total']))
            y -= 22

        y -= 10
        p.setStrokeColor(colors.HexColor("#e2e8f0"))
        p.line(300, y, width - 40, y)
        y -= 20

        p.setFont("Helvetica", 10)
        p.setFillColor(grey)
        p.drawString(300, y, "Subtotal:")
        p.setFillColor(dark)
        p.drawRightString(width - 40, y, indian_currency(quotation['subtotal']))
        y -= 18

        p.setFillColor(grey)
        p.drawString(300, y, f"Discount ({quotation['discount_pct']}%):")
        p.setFillColor(dark)
        p.drawRightString(width - 40, y, f"- {indian_currency(quotation['discount_amount'])}")
        y -= 18

        p.setFillColor(grey)
        p.drawString(300, y, f"Tax ({quotation['tax_pct']}%):")
        p.setFillColor(dark)
        p.drawRightString(width - 40, y, indian_currency(quotation['tax_amount']))
        y -= 25

        p.setStrokeColor(blue)
        p.setLineWidth(1.5)
        p.line(300, y, width - 40, y)
        y -= 20

        p.setFont("Helvetica-Bold", 13)
        p.setFillColor(dark)
        p.drawString(300, y, "GRAND TOTAL:")
        p.setFillColor(blue)
        p.drawRightString(width - 40, y, indian_currency(quotation['grand_total']))

        y -= 25
        p.setFont("Helvetica", 9)
        p.setFillColor(grey)
        words = amount_in_words(float(quotation['grand_total']))
        p.drawString(40, y, f"Amount in Words: {words}")

        if quotation.get('notes'):
            y -= 30
            p.setStrokeColor(colors.HexColor("#e2e8f0"))
            p.line(40, y, width - 40, y)
            y -= 18
            p.setFont("Helvetica-Bold", 10)
            p.setFillColor(dark)
            p.drawString(40, y, "Notes:")
            y -= 15
            p.setFont("Helvetica", 9)
            p.setFillColor(grey)
            for line in quotation['notes'].split('\n')[:3]:
                p.drawString(50, y, line[:90])
                y -= 13

        if quotation.get('terms'):
            y -= 20
            p.setFont("Helvetica-Bold", 10)
            p.setFillColor(dark)
            p.drawString(40, y, "Terms & Conditions:")
            y -= 15
            p.setFont("Helvetica", 8)
            p.setFillColor(grey)
            for line in quotation['terms'].split('\n')[:5]:
                p.drawString(50, y, line[:95])
                y -= 12

        p.setFont("Helvetica-Oblique", 8)
        p.setFillColor(colors.HexColor("#94a3b8"))
        p.drawCentredString(width / 2, 40, f"Generated by {company_name} ERP  |  This is a system-generated document.")

        p.showPage()
        p.save()
        buffer.seek(0)

        safe_num = quotation['quote_number'].replace(' ', '_')
        return send_file(buffer, as_attachment=True,
                         download_name=f"{safe_num}.pdf",
                         mimetype='application/pdf')
    except Exception as e:
        logger.error("Generate quotation PDF error: %s", e)
        return "Error generating PDF", 500


@quotation_bp.route('/api/quotations')
@login_required
def api_quotations():
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT q.quote_id, q.quote_number, q.subject, q.grand_total, q.status,
                           q.created_at, q.valid_until, c.name as customer_name
                    FROM quotation q
                    LEFT JOIN customer c ON q.customer_id = c.customer_id
                    ORDER BY q.created_at DESC
                """)
                quotations = cursor.fetchall()

        for q in quotations:
            for k, v in q.items():
                if hasattr(v, 'isoformat'):
                    q[k] = v.isoformat()
                elif isinstance(v, float):
                    q[k] = str(v)

        return jsonify({'quotations': quotations})
    except Exception as e:
        logger.error("API quotations error: %s", e)
        return jsonify({'error': 'Failed to fetch quotations.'}), 500
