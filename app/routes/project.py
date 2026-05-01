from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import pymysql

project_bp = Blueprint('project', __name__)

from app.db import get_db_connection

@project_bp.route('/projects')
def project_board():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    search_query = request.args.get('q', '')
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Fetch tasks with optional search
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
            
            # Fetch dropdown data
            cursor.execute("SELECT project_id, name FROM project")
            projects = cursor.fetchall()
            
            cursor.execute("SELECT user_id, name FROM users WHERE role_id != 1") # Exclude admin from assignee maybe
            users = cursor.fetchall()
            
        conn.close()

        # Group tasks for Kanban
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
                # Default fallback
                kanban['Pending'].append(task)

        return render_template('projects.html', kanban=kanban, projects=projects, users=users)

    except Exception as e:
        flash(f'Database error: {str(e)}', 'danger')
        return render_template('projects.html', kanban={'Pending':[],'In Progress':[],'Blocked':[],'Completed':[]}, projects=[], users=[])

@project_bp.route('/tasks/add', methods=['POST'])
def add_task():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    title = request.form.get('title')
    project_id = request.form.get('project_id')
    assigned_to = request.form.get('assigned_to')
    deadline = request.form.get('deadline')
    
    # If no project is selected, let's create a default or handle it gracefully
    if not project_id:
        project_id = None
        
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO task (project_id, assigned_to, title, deadline, status)
                VALUES (%s, %s, %s, %s, 'Pending')
            """, (project_id, assigned_to, title, deadline))
        conn.commit()
        conn.close()
        flash('New task created successfully.', 'success')
    except Exception as e:
        flash(f'Error creating task: {str(e)}', 'danger')

    return redirect(url_for('project.project_board'))

@project_bp.route('/tasks/update_status', methods=['POST'])
def update_task_status():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

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
