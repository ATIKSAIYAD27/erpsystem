from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file, jsonify, abort
import os
import uuid
import mimetypes
from datetime import datetime
from werkzeug.utils import secure_filename
import logging
from app.db import get_db_connection
from app.utils import login_required, admin_required, log_audit

documents_bp = Blueprint('documents', __name__)
logger = logging.getLogger(__name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'uploads')
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB

ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'txt', 'csv', 'json', 'xml',
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg',
    'zip', 'rar', '7z',
    'mp4', 'webm', 'mp3', 'wav'
}

MIME_ICONS = {
    'pdf': 'bi-file-earmark-pdf',
    'doc': 'bi-file-earmark-word', 'docx': 'bi-file-earmark-word',
    'xls': 'bi-file-earmark-excel', 'xlsx': 'bi-file-earmark-excel',
    'ppt': 'bi-file-earmark-slides', 'pptx': 'bi-file-earmark-slides',
    'png': 'bi-file-earmark-image', 'jpg': 'bi-file-earmark-image',
    'jpeg': 'bi-file-earmark-image', 'gif': 'bi-file-earmark-image',
    'svg': 'bi-file-earmark-image', 'webp': 'bi-file-earmark-image',
    'zip': 'bi-file-earmark-zip', 'rar': 'bi-file-earmark-zip',
    'mp4': 'bi-file-earmark-play', 'webm': 'bi-file-earmark-play',
    'mp3': 'bi-file-earmark-music', 'wav': 'bi-file-earmark-music',
    'txt': 'bi-file-earmark-text', 'csv': 'bi-file-earmark-text',
    'json': 'bi-file-earmark-code', 'xml': 'bi-file-earmark-code',
}


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _format_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _get_icon(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return MIME_ICONS.get(ext, 'bi-file-earmark')


@documents_bp.route('/documents')
@login_required
def document_list():
    search_query = request.args.get('q', '')
    category_filter = request.args.get('category', '')

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            base_sql = """
                SELECT d.*, u.name as uploaded_by_name,
                       (SELECT COUNT(*) FROM document_share ds WHERE ds.doc_id = d.doc_id) as share_count
                FROM document d
                LEFT JOIN users u ON d.uploaded_by = u.user_id
                WHERE (d.uploaded_by = %s OR d.is_public = TRUE
                       OR d.doc_id IN (SELECT doc_id FROM document_share WHERE user_id = %s))
            """
            params = [session['user_id'], session['user_id']]

            if search_query:
                base_sql += " AND (d.original_name LIKE %s OR d.description LIKE %s)"
                params.extend([f'%{search_query}%', f'%{search_query}%'])

            if category_filter:
                base_sql += " AND d.category = %s"
                params.append(category_filter)

            base_sql += " ORDER BY d.uploaded_at DESC"

            cursor.execute(base_sql, params)
            documents = cursor.fetchall()

            cursor.execute("SELECT DISTINCT category FROM document WHERE category IS NOT NULL ORDER BY category")
            categories = [row['category'] for row in cursor.fetchall()]

        conn.close()

        for doc in documents:
            if doc.get('uploaded_at'):
                doc['uploaded_at'] = doc['uploaded_at'].strftime('%d/%m/%Y %H:%M')
            doc['icon'] = _get_icon(doc['original_name'])
            doc['size_formatted'] = _format_size(doc['file_size'])

        return render_template('documents.html',
                               documents=documents,
                               categories=categories,
                               search_query=search_query,
                               category_filter=category_filter)
    except Exception as e:
        logger.error("Document list error: %s", e)
        flash('An error occurred.', 'danger')
        return render_template('documents.html', documents=[], categories=[], search_query=search_query, category_filter=category_filter)


@documents_bp.route('/documents/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('documents.document_list'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('documents.document_list'))

    if not _allowed_file(file.filename):
        flash('File type not allowed.', 'danger')
        return redirect(url_for('documents.document_list'))

    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size > MAX_FILE_SIZE:
        flash(f'File too large. Maximum size is {_format_size(MAX_FILE_SIZE)}.', 'danger')
        return redirect(url_for('documents.document_list'))

    category = request.form.get('category', '').strip() or None
    description = request.form.get('description', '').strip() or None
    is_public = 1 if request.form.get('is_public') else 0

    original_name = secure_filename(file.filename)
    if not original_name or original_name == 'file':
        original_name = file.filename.replace(' ', '_')

    ext = original_name.rsplit('.', 1)[1].lower() if '.' in original_name else 'bin'
    stored_name = f"{uuid.uuid4().hex}.{ext}"

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file_path = os.path.join(UPLOAD_FOLDER, stored_name)
    file.save(file_path)

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO document (original_name, stored_name, file_size, mime_type, category, description, is_public, uploaded_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (original_name, stored_name, file_size, mimetypes.guess_type(original_name)[0], category, description, is_public, session['user_id']))
        conn.commit()
        conn.close()

        log_audit(session['user_id'], f"Uploaded document: {original_name}")
        flash(f'"{original_name}" uploaded successfully.', 'success')
    except Exception as e:
        logger.error("Upload error: %s", e)
        flash('An error occurred during upload.', 'danger')

    return redirect(url_for('documents.document_list'))


@documents_bp.route('/documents/download/<int:doc_id>')
@login_required
def download(doc_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM document WHERE doc_id = %s", (doc_id,))
            doc = cursor.fetchone()

            if not doc:
                conn.close()
                abort(404)

            if doc['uploaded_by'] != session['user_id'] and not doc['is_public']:
                cursor.execute(
                    "SELECT 1 FROM document_share WHERE doc_id = %s AND user_id = %s",
                    (doc_id, session['user_id'])
                )
                shared = cursor.fetchone()
                conn.close()
                if not shared:
                    abort(403)
            else:
                conn.close()

        file_path = os.path.join(UPLOAD_FOLDER, doc['stored_name'])
        if not os.path.exists(file_path):
            flash('File not found on server.', 'danger')
            return redirect(url_for('documents.document_list'))

        log_audit(session['user_id'], f"Downloaded document: {doc['original_name']}")
        return send_file(file_path, as_attachment=True, download_name=doc['original_name'])
    except Exception as e:
        logger.error("Download error: %s", e)
        flash('An error occurred.', 'danger')
        return redirect(url_for('documents.document_list'))


@documents_bp.route('/documents/delete/<int:doc_id>', methods=['POST'])
@login_required
def delete(doc_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM document WHERE doc_id = %s", (doc_id,))
            doc = cursor.fetchone()

            if not doc:
                flash('Document not found.', 'danger')
                conn.close()
                return redirect(url_for('documents.document_list'))

            if doc['uploaded_by'] != session['user_id'] and session.get('role_name') != 'Admin':
                flash('Permission denied.', 'danger')
                conn.close()
                return redirect(url_for('documents.document_list'))

            file_path = os.path.join(UPLOAD_FOLDER, doc['stored_name'])
            if os.path.exists(file_path):
                os.remove(file_path)

            cursor.execute("DELETE FROM document_share WHERE doc_id = %s", (doc_id,))
            cursor.execute("DELETE FROM document WHERE doc_id = %s", (doc_id,))
        conn.commit()
        conn.close()

        log_audit(session['user_id'], f"Deleted document: {doc['original_name']}")
        flash('Document deleted.', 'success')
    except Exception as e:
        logger.error("Delete error: %s", e)
        flash('An error occurred.', 'danger')

    return redirect(url_for('documents.document_list'))


@documents_bp.route('/documents/share/<int:doc_id>', methods=['POST'])
@login_required
def share(doc_id):
    user_id_to_share = request.form.get('user_id')
    if not user_id_to_share:
        flash('Select a user to share with.', 'danger')
        return redirect(url_for('documents.document_list'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT uploaded_by FROM document WHERE doc_id = %s", (doc_id,))
            doc = cursor.fetchone()
            if not doc or doc['uploaded_by'] != session['user_id']:
                flash('Permission denied.', 'danger')
                conn.close()
                return redirect(url_for('documents.document_list'))

            cursor.execute(
                "INSERT INTO document_share (doc_id, user_id, shared_by) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (doc_id, user_id_to_share, session['user_id'])
            )
        conn.commit()
        conn.close()
        flash('Document shared successfully.', 'success')
    except Exception as e:
        logger.error("Share error: %s", e)
        flash('An error occurred.', 'danger')

    return redirect(url_for('documents.document_list'))


@documents_bp.route('/api/documents', methods=['GET'])
@login_required
def api_list():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT d.doc_id, d.original_name, d.file_size, d.category, d.description,
                       d.is_public, d.uploaded_at, u.name as uploaded_by_name
                FROM document d
                LEFT JOIN users u ON d.uploaded_by = u.user_id
                WHERE d.uploaded_by = %s OR d.is_public = TRUE
                ORDER BY d.uploaded_at DESC
            """, (session['user_id'],))
            docs = cursor.fetchall()
        conn.close()

        for d in docs:
            if d.get('uploaded_at'):
                d['uploaded_at'] = d['uploaded_at'].isoformat()
            d['icon'] = _get_icon(d['original_name'])
            d['size_formatted'] = _format_size(d['file_size'])

        return jsonify({'documents': docs})
    except Exception as e:
        logger.error("API documents error: %s", e)
        return jsonify({'error': 'Failed to fetch documents.'}), 500
