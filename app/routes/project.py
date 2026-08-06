from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import pymysql
from app.utils import login_required, admin_required, manager_or_admin_required, log_audit

project_bp = Blueprint('project', __name__)

from app.db import get_db_connection

@project_bp.route('/projects')
@manager_or_admin_required
def project_board():
    search_query = request.args.get('q', '')
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if search_query:
                sql = """
                    SELECT t.task_id, t.title, t.deadline, t.status, 
                           u.name as assignee, p.name as project_name
                    FROM task t
                    LEFT JOIN users u ON t.assigned_to = u.user_id
                    LEFT JOIN project p ON t.project_id = p.project_id
                    WHERE t.title LIKE %s OR u.name LIKE %s OR p.name LIKE %s
                """
                cursor.execute(sql, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
            else:
                sql = """
                    SELECT t.task_id, t.title, t.deadline, t.status, 
                           u.name as assignee, p.name as project_name
                    FROM task t
                    LEFT JOIN users u ON t.assigned_to = u.user_id
                    LEFT JOIN project p ON t.project_id = p.project_id
                """
                cursor.execute(sql)
            all_tasks = cursor.fetchall()
            
            cursor.execute("SELECT project_id, name FROM project ORDER BY name")
            projects = cursor.fetchall()
            
            cursor.execute("SELECT user_id, name FROM users WHERE role_id != 1")
            users = cursor.fetchall()
            
        conn.close()

        kanban = {
            'Pending': [],
            'In Progress': [],
            'Blocked': [],
            'Completed': []
        }
        
        for task in all_tasks:
            if task['status'] in kanban:
                kanban[task['status']].append(task)
            else:
                kanban['Pending'].append(task)

        return render_template('projects.html', kanban=kanban, projects=projects, users=users)

    except Exception as e:
        flash(f'Database error: {str(e)}', 'danger')
        return render_template('projects.html', kanban={'Pending':[],'In Progress':[],'Blocked':[],'Completed':[]}, projects=[], users=[])

@project_bp.route('/projects/add', methods=['POST'])
@manager_or_admin_required
def add_project():
    name = request.form.get('name')
    description = request.form.get('description', '')

    if not name:
        flash('Project name is required.', 'danger')
        return redirect(url_for('project.project_board'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO project (name, description)
                VALUES (%s, %s)
            """, (name, description))
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Created project: {name}")
        flash('Project created successfully.', 'success')
    except Exception as e:
        flash(f'Error creating project: {str(e)}', 'danger')

    return redirect(url_for('project.project_board'))

@project_bp.route('/projects/edit/<int:project_id>', methods=['POST'])
@manager_or_admin_required
def edit_project(project_id):
    name = request.form.get('name')
    description = request.form.get('description', '')

    if not name:
        flash('Project name is required.', 'danger')
        return redirect(url_for('project.project_board'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE project SET name=%s, description=%s WHERE project_id=%s
            """, (name, description, project_id))
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Updated project {project_id}: {name}")
        flash('Project updated successfully.', 'success')
    except Exception as e:
        flash(f'Error updating project: {str(e)}', 'danger')

    return redirect(url_for('project.project_board'))

@project_bp.route('/projects/delete/<int:project_id>')
@admin_required
def delete_project(project_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("UPDATE task SET project_id = NULL WHERE project_id = %s", (project_id,))
            cursor.execute("DELETE FROM project WHERE project_id = %s", (project_id,))
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Deleted project {project_id}")
        flash('Project deleted successfully. Tasks have been unlinked.', 'success')
    except Exception as e:
        flash(f'Error deleting project: {str(e)}', 'danger')

    return redirect(url_for('project.project_board'))

@project_bp.route('/tasks/add', methods=['POST'])
@manager_or_admin_required
def add_task():
    title = request.form.get('title')
    project_id = request.form.get('project_id')
    assigned_to = request.form.get('assigned_to')
    deadline = request.form.get('deadline')
    
    if not project_id:
        project_id = None
        
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO task (project_id, assigned_to, title, deadline, status)
                VALUES (%s, %s, %s, %s, 'Pending')
            """, (project_id, assigned_to, title, deadline))
            
            if assigned_to:
                from app.utils import create_notification
                create_notification(assigned_to, f"New task assigned: {title}. Deadline: {deadline}", 'info')
                
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Created task: {title}")
        flash('New task created successfully.', 'success')
    except Exception as e:
        flash(f'Error creating task: {str(e)}', 'danger')

    return redirect(url_for('project.project_board'))

@project_bp.route('/tasks/update_status', methods=['POST'])
@manager_or_admin_required
def update_task_status():
    data = request.json
    task_id = data.get('task_id')
    new_status = data.get('status')
    
    if not task_id or not new_status:
        return jsonify({'success': False, 'message': 'Missing data'}), 400
        
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE task 
                SET status = %s 
                WHERE task_id = %s
            """, (new_status, task_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@project_bp.route('/tasks/delete/<int:task_id>')
@admin_required
def delete_task(task_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM task WHERE task_id = %s", (task_id,))
        conn.commit()
        conn.close()
        log_audit(session['user_id'], f"Deleted task {task_id}")
        flash('Task deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting task: {str(e)}', 'danger')

    return redirect(url_for('project.project_board'))
