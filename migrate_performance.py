"""
Database Performance Optimization Migration
Adds indexes for faster queries and better performance.
"""
import pymysql
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def get_connection():
    return pymysql.connect(
        host=os.environ.get('DB_HOST', os.environ.get('MYSQLHOST', '127.0.0.1')),
        port=int(os.environ.get('DB_PORT', os.environ.get('MYSQLPORT', 3306))),
        user=os.environ.get('DB_USER', os.environ.get('MYSQLUSER', 'root')),
        password=os.environ.get('DB_PASSWORD', os.environ.get('MYSQLPASSWORD', '')),
        database=os.environ.get('DB_NAME', os.environ.get('MYSQLDATABASE', 'erpsystem')),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
    )


INDEXES = [
    # Employee performance
    ("idx_employee_user_id", "ALTER TABLE employee ADD INDEX idx_employee_user_id (user_id)"),
    ("idx_employee_department", "ALTER TABLE employee ADD INDEX idx_employee_department (department)"),
    
    # Sale performance (most queried)
    ("idx_sale_date", "ALTER TABLE sale ADD INDEX idx_sale_date (sale_date)"),
    ("idx_sale_customer", "ALTER TABLE sale ADD INDEX idx_sale_customer (customer_id)"),
    ("idx_sale_product", "ALTER TABLE sale ADD INDEX idx_sale_product (product_id)"),
    ("idx_sale_date_amount", "ALTER TABLE sale ADD INDEX idx_sale_date_amount (sale_date, total_amount)"),
    
    # Attendance performance
    ("idx_attendance_emp_date", "ALTER TABLE attendance ADD INDEX idx_attendance_emp_date (emp_id, `date`)"),
    ("idx_attendance_date", "ALTER TABLE attendance ADD INDEX idx_attendance_date (`date`)"),
    
    # Task performance
    ("idx_task_status", "ALTER TABLE task ADD INDEX idx_task_status (status)"),
    ("idx_task_assignee", "ALTER TABLE task ADD INDEX idx_task_assignee (assigned_to)"),
    ("idx_task_deadline", "ALTER TABLE task ADD INDEX idx_task_deadline (deadline)"),
    
    # Expense performance
    ("idx_expense_date", "ALTER TABLE expense ADD INDEX idx_expense_date (`date`)"),
    ("idx_expense_category", "ALTER TABLE expense ADD INDEX idx_expense_category (category)"),
    ("idx_expense_department", "ALTER TABLE expense ADD INDEX idx_expense_department (department)"),
    
    # Product performance
    ("idx_product_sku", "ALTER TABLE product ADD INDEX idx_product_sku (sku)"),
    ("idx_product_stock", "ALTER TABLE product ADD INDEX idx_product_stock (quantity, reorder_level)"),
    
    # Leave performance
    ("idx_leaves_emp", "ALTER TABLE leaves ADD INDEX idx_leaves_emp (emp_id)"),
    ("idx_leaves_status", "ALTER TABLE leaves ADD INDEX idx_leaves_status (status)"),
    ("idx_leaves_dates", "ALTER TABLE leaves ADD INDEX idx_leaves_dates (start_date, end_date)"),
    
    # Notifications
    ("idx_notifications_user_read", "ALTER TABLE notifications ADD INDEX idx_notifications_user_read (user_id, is_read)"),
    
    # Messages
    ("idx_messages_receiver", "ALTER TABLE messages ADD INDEX idx_messages_receiver (receiver_id, is_read)"),
    
    # Payroll
    ("idx_payroll_emp", "ALTER TABLE payroll ADD INDEX idx_payroll_emp (emp_id)"),
    
    # Quotation
    ("idx_quotation_status", "ALTER TABLE quotation ADD INDEX idx_quotation_status (status)"),
    ("idx_quotation_customer", "ALTER TABLE quotation ADD INDEX idx_quotation_customer (customer_id)"),
    
    # Purchase orders
    ("idx_po_status", "ALTER TABLE purchase_order ADD INDEX idx_po_status (status)"),
    ("idx_po_supplier", "ALTER TABLE purchase_order ADD INDEX idx_po_supplier (supplier_id)"),
    
    # Budget
    ("idx_budget_dept_year", "ALTER TABLE budget ADD INDEX idx_budget_dept_year (department, year)"),
    
    # Sales pipeline
    ("idx_pipeline_stage", "ALTER TABLE sales_pipeline ADD INDEX idx_pipeline_stage (stage)"),
    
    # Risk
    ("idx_risk_level", "ALTER TABLE risk ADD INDEX idx_risk_level (risk_level)"),
    ("idx_risk_status", "ALTER TABLE risk ADD INDEX idx_risk_status (status)"),
    
    # Calendar events
    ("idx_calendar_date", "ALTER TABLE calendar_event ADD INDEX idx_calendar_date (start_date)"),
    
    # Audit log
    ("idx_audit_user", "ALTER TABLE audit_log ADD INDEX idx_audit_user (user_id)"),
    ("idx_audit_timestamp", "ALTER TABLE audit_log ADD INDEX idx_audit_timestamp (created_at)"),
    
    # Document shares
    ("idx_doc_share_user", "ALTER TABLE document_share ADD INDEX idx_doc_share_user (user_id)"),
]


def migrate():
    conn = get_connection()
    cursor = conn.cursor()
    
    created = 0
    skipped = 0
    errors = 0
    
    for name, sql in INDEXES:
        try:
            cursor.execute(sql)
            conn.commit()
            created += 1
            print(f"  [OK] Created index: {name}")
        except pymysql.err.OperationalError as e:
            if "Duplicate key name" in str(e) or "already exists" in str(e):
                skipped += 1
                print(f"  [SKIP] Index already exists: {name}")
            else:
                errors += 1
                print(f"  [ERROR] {name}: {e}")
        except Exception as e:
            errors += 1
            print(f"  [ERROR] {name}: {e}")
    
    cursor.close()
    conn.close()
    
    print(f"\nMigration complete: {created} created, {skipped} skipped, {errors} errors")


if __name__ == '__main__':
    print("Running database performance optimization migration...")
    migrate()
