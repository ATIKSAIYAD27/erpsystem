import pymysql
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()


def get_ssl_config():
    mysql_ssl_ca = os.environ.get('MYSQL_ROOT_CERT')
    if mysql_ssl_ca:
        return {'ca': mysql_ssl_ca}
    host = os.environ.get('DB_HOST', os.environ.get('MYSQLHOST', '127.0.0.1'))
    if host not in ('127.0.0.1', 'localhost'):
        return {}
    return None


def get_db_connection():
    host = os.environ.get('DB_HOST', os.environ.get('MYSQLHOST', '127.0.0.1'))
    port = int(os.environ.get('DB_PORT', os.environ.get('MYSQLPORT', 3306)))
    user = os.environ.get('DB_USER', os.environ.get('MYSQLUSER', 'root'))
    password = os.environ.get('DB_PASSWORD', os.environ.get('MYSQLPASSWORD', ''))
    database = os.environ.get('DB_NAME', os.environ.get('MYSQLDATABASE', 'erpsystem'))
    ssl = get_ssl_config()

    try:
        return pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
            ssl=ssl,
        )
    except Exception as primary_error:
        fallback_host = 'localhost' if host == '127.0.0.1' else '127.0.0.1'
        try:
            return pymysql.connect(
                host=fallback_host,
                port=port,
                user=user,
                password=password,
                database=database,
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=10,
            )
        except Exception:
            raise primary_error


def init_db():
    print("Initializing Nexus ERP Database...")

    db_name = os.environ.get('DB_NAME', os.environ.get('MYSQLDATABASE', 'erpsystem'))

    try:
        temp_conn = pymysql.connect(
            host=os.environ.get('DB_HOST', os.environ.get('MYSQLHOST', 'localhost')),
            port=int(os.environ.get('DB_PORT', os.environ.get('MYSQLPORT', 3306))),
            user=os.environ.get('DB_USER', os.environ.get('MYSQLUSER', 'root')),
            password=os.environ.get('DB_PASSWORD', os.environ.get('MYSQLPASSWORD', '')),
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
            ssl=get_ssl_config(),
        )
        with temp_conn.cursor() as cursor:
            print(f"Checking for database '{db_name}'...")
            safe_db_name = db_name.replace('`', '``')
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{safe_db_name}`")
        temp_conn.commit()
        temp_conn.close()
        print(f"Database '{db_name}' verified.")

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS role (
                    role_id INT AUTO_INCREMENT PRIMARY KEY,
                    role_name VARCHAR(50) NOT NULL UNIQUE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100),
                    email VARCHAR(100) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    role_id INT,
                    totp_secret VARCHAR(64),
                    totp_enabled BOOLEAN DEFAULT FALSE,
                    api_token VARCHAR(128),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (role_id) REFERENCES role(role_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS employee (
                    emp_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    job_title VARCHAR(100),
                    department VARCHAR(100),
                    phone VARCHAR(20),
                    salary DECIMAL(10, 2),
                    hire_date DATE,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attendance (
                    attendance_id INT AUTO_INCREMENT PRIMARY KEY,
                    emp_id INT,
                    date DATE,
                    status VARCHAR(20),
                    check_in TIME,
                    check_out TIME,
                    FOREIGN KEY (emp_id) REFERENCES employee(emp_id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leaves (
                    leave_id INT AUTO_INCREMENT PRIMARY KEY,
                    emp_id INT,
                    leave_type VARCHAR(50),
                    start_date DATE,
                    end_date DATE,
                    status VARCHAR(20) DEFAULT 'Pending',
                    reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (emp_id) REFERENCES employee(emp_id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leave_balance (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    emp_id INT,
                    leave_type VARCHAR(50),
                    total_days INT DEFAULT 12,
                    used_days INT DEFAULT 0,
                    year INT,
                    FOREIGN KEY (emp_id) REFERENCES employee(emp_id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS payroll (
                    payroll_id INT AUTO_INCREMENT PRIMARY KEY,
                    emp_id INT,
                    month INT,
                    year INT,
                    basic DECIMAL(10, 2),
                    deductions DECIMAL(10, 2) DEFAULT 0,
                    net_pay DECIMAL(10, 2),
                    FOREIGN KEY (emp_id) REFERENCES employee(emp_id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS customer (
                    customer_id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100),
                    phone VARCHAR(20),
                    address TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS product (
                    product_id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    sku VARCHAR(50) UNIQUE,
                    description TEXT,
                    unit_price DECIMAL(10, 2),
                    quantity INT DEFAULT 0,
                    reorder_level INT DEFAULT 10
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sale (
                    sale_id INT AUTO_INCREMENT PRIMARY KEY,
                    customer_id INT,
                    product_id INT,
                    quantity INT,
                    total_amount DECIMAL(10, 2),
                    sale_date DATE,
                    FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
                    FOREIGN KEY (product_id) REFERENCES product(product_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project (
                    project_id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    status VARCHAR(50) DEFAULT 'Active'
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task (
                    task_id INT AUTO_INCREMENT PRIMARY KEY,
                    project_id INT,
                    assigned_to INT,
                    title VARCHAR(200),
                    description TEXT,
                    status VARCHAR(50) DEFAULT 'Pending',
                    deadline DATE,
                    FOREIGN KEY (project_id) REFERENCES project(project_id) ON DELETE SET NULL,
                    FOREIGN KEY (assigned_to) REFERENCES users(user_id) ON DELETE SET NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id INT AUTO_INCREMENT PRIMARY KEY,
                    sender_id INT,
                    receiver_id INT,
                    subject VARCHAR(255),
                    content TEXT,
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sender_id) REFERENCES users(user_id),
                    FOREIGN KEY (receiver_id) REFERENCES users(user_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    message TEXT NOT NULL,
                    type VARCHAR(20) DEFAULT 'info',
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS expense (
                    expense_id INT AUTO_INCREMENT PRIMARY KEY,
                    category VARCHAR(100),
                    department VARCHAR(100) DEFAULT 'General',
                    amount DECIMAL(10, 2),
                    date DATE,
                    description TEXT,
                    created_by INT,
                    FOREIGN KEY (created_by) REFERENCES users(user_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    action TEXT,
                    ip_address VARCHAR(45),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS supplier (
                    supplier_id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100),
                    phone VARCHAR(20),
                    address TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchase_order (
                    po_id INT AUTO_INCREMENT PRIMARY KEY,
                    supplier_id INT,
                    total_amount DECIMAL(10, 2),
                    status VARCHAR(50) DEFAULT 'Pending',
                    order_date DATE,
                    expected_delivery DATE,
                    created_by INT,
                    FOREIGN KEY (supplier_id) REFERENCES supplier(supplier_id),
                    FOREIGN KEY (created_by) REFERENCES users(user_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchase_order_item (
                    item_id INT AUTO_INCREMENT PRIMARY KEY,
                    po_id INT,
                    product_id INT,
                    quantity INT,
                    unit_cost DECIMAL(10, 2),
                    FOREIGN KEY (po_id) REFERENCES purchase_order(po_id) ON DELETE CASCADE,
                    FOREIGN KEY (product_id) REFERENCES product(product_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS company_settings (
                    id INT PRIMARY KEY DEFAULT 1,
                    company_name VARCHAR(200),
                    address TEXT,
                    phone VARCHAR(20),
                    email VARCHAR(100),
                    tax_rate DECIMAL(5, 2) DEFAULT 0,
                    currency VARCHAR(10) DEFAULT 'INR'
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document (
                    doc_id INT AUTO_INCREMENT PRIMARY KEY,
                    original_name VARCHAR(255) NOT NULL,
                    stored_name VARCHAR(255) NOT NULL,
                    file_size BIGINT NOT NULL,
                    mime_type VARCHAR(100),
                    category VARCHAR(100),
                    description TEXT,
                    is_public BOOLEAN DEFAULT FALSE,
                    uploaded_by INT,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (uploaded_by) REFERENCES users(user_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quotation (
                    quote_id INT AUTO_INCREMENT PRIMARY KEY,
                    quote_number VARCHAR(20) NOT NULL UNIQUE,
                    customer_id INT,
                    subject VARCHAR(255),
                    notes TEXT,
                    terms TEXT,
                    subtotal DECIMAL(12, 2) DEFAULT 0,
                    discount_pct DECIMAL(5, 2) DEFAULT 0,
                    discount_amount DECIMAL(12, 2) DEFAULT 0,
                    tax_pct DECIMAL(5, 2) DEFAULT 0,
                    tax_amount DECIMAL(12, 2) DEFAULT 0,
                    grand_total DECIMAL(12, 2) DEFAULT 0,
                    valid_until DATE,
                    status VARCHAR(20) DEFAULT 'Draft',
                    created_by INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
                    FOREIGN KEY (created_by) REFERENCES users(user_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quotation_item (
                    item_id INT AUTO_INCREMENT PRIMARY KEY,
                    quote_id INT,
                    product_id INT,
                    quantity INT DEFAULT 1,
                    unit_price DECIMAL(10, 2) DEFAULT 0,
                    discount DECIMAL(10, 2) DEFAULT 0,
                    line_total DECIMAL(12, 2) DEFAULT 0,
                    FOREIGN KEY (quote_id) REFERENCES quotation(quote_id) ON DELETE CASCADE,
                    FOREIGN KEY (product_id) REFERENCES product(product_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS calendar_event (
                    event_id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE,
                    event_type VARCHAR(50) DEFAULT 'event',
                    created_by INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (created_by) REFERENCES users(user_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS budget (
                    budget_id INT AUTO_INCREMENT PRIMARY KEY,
                    department VARCHAR(100) NOT NULL,
                    allocated_amount DECIMAL(12, 2) DEFAULT 0,
                    fiscal_year INT NOT NULL,
                    created_by INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_dept_year (department, fiscal_year),
                    FOREIGN KEY (created_by) REFERENCES users(user_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workflow (
                    workflow_id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    description TEXT,
                    trigger_type VARCHAR(50) DEFAULT 'manual',
                    threshold_amount DECIMAL(12, 2) DEFAULT 0,
                    approver_role VARCHAR(50) DEFAULT 'Admin',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_by INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (created_by) REFERENCES users(user_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workflow_request (
                    request_id INT AUTO_INCREMENT PRIMARY KEY,
                    workflow_id INT,
                    entity_type VARCHAR(50),
                    entity_id INT DEFAULT 0,
                    amount DECIMAL(12, 2) DEFAULT 0,
                    notes TEXT,
                    status VARCHAR(20) DEFAULT 'Pending',
                    requested_by INT,
                    approved_by INT,
                    approved_at TIMESTAMP NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (workflow_id) REFERENCES workflow(workflow_id),
                    FOREIGN KEY (requested_by) REFERENCES users(user_id),
                    FOREIGN KEY (approved_by) REFERENCES users(user_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS risk (
                    risk_id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    category VARCHAR(100),
                    risk_level VARCHAR(20) DEFAULT 'Medium',
                    probability INT DEFAULT 3,
                    impact INT DEFAULT 3,
                    risk_score INT DEFAULT 0,
                    mitigation_plan TEXT,
                    assigned_to INT,
                    identified_by INT,
                    identified_date DATE,
                    status VARCHAR(50) DEFAULT 'Identified',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (assigned_to) REFERENCES users(user_id),
                    FOREIGN KEY (identified_by) REFERENCES users(user_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sales_pipeline (
                    deal_id INT AUTO_INCREMENT PRIMARY KEY,
                    deal_name VARCHAR(255) NOT NULL,
                    customer_id INT,
                    deal_value DECIMAL(12, 2) DEFAULT 0,
                    stage VARCHAR(50) DEFAULT 'Lead',
                    owner_id INT,
                    expected_close DATE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
                    FOREIGN KEY (owner_id) REFERENCES users(user_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sales_target (
                    target_id INT AUTO_INCREMENT PRIMARY KEY,
                    month INT NOT NULL,
                    year INT NOT NULL,
                    target_amount DECIMAL(12, 2) DEFAULT 0,
                    set_by INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_month_year (month, year),
                    FOREIGN KEY (set_by) REFERENCES users(user_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_share (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    doc_id INT,
                    user_id INT,
                    shared_by INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (doc_id) REFERENCES document(doc_id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (shared_by) REFERENCES users(user_id),
                    UNIQUE KEY unique_share (doc_id, user_id)
                )
            """)

            cursor.execute("SELECT COUNT(*) as count FROM role")
            if cursor.fetchone()['count'] == 0:
                print("Seeding roles...")
                cursor.execute("INSERT INTO role (role_name) VALUES ('Admin'), ('Manager'), ('Employee')")

            cursor.execute("SELECT COUNT(*) as count FROM users")
            if cursor.fetchone()['count'] == 0:
                print("Seeding admin user...")
                admin_pw = generate_password_hash('admin123')
                cursor.execute(
                    "INSERT INTO users (name, email, password_hash, role_id) VALUES (%s, %s, %s, %s)",
                    ('Administrator', 'admin@nexus-erp.in', admin_pw, 1)
                )

        conn.commit()
        conn.close()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Error during database initialization: {e}")


if __name__ == "__main__":
    init_db()
