import pymysql
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# Load .env file for local development
load_dotenv()

def get_db_connection():
    return pymysql.connect(
        host=os.environ.get('DB_HOST', os.environ.get('MYSQLHOST', 'localhost')),
        port=int(os.environ.get('DB_PORT', os.environ.get('MYSQLPORT', 3306))),
        user=os.environ.get('DB_USER', os.environ.get('MYSQLUSER', 'root')),
        password=os.environ.get('DB_PASSWORD', os.environ.get('MYSQLPASSWORD', '')),
        database=os.environ.get('DB_NAME', os.environ.get('MYSQLDATABASE', 'erpsystem')),
        cursorclass=pymysql.cursors.DictCursor
    )

def init_db():
    print("🚀 Initializing Database...")
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 1. Roles Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS role (
                    role_id INT AUTO_INCREMENT PRIMARY KEY,
                    role_name VARCHAR(50) NOT NULL UNIQUE
                )
            """)
            
            # 2. Users Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100),
                    email VARCHAR(100) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    role_id INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 3. Employee Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS employee (
                    emp_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    job_title VARCHAR(100),
                    department VARCHAR(100),
                    salary DECIMAL(10, 2),
                    hire_date DATE,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)
            
            # 4. Attendance Table
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
            
            # 5. Leaves Table
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
            
            # 6. Payroll Table
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
            
            # 7. Customer Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS customer (
                    customer_id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100),
                    phone VARCHAR(20),
                    address TEXT
                )
            """)
            
            # 8. Product Table
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
            
            # 9. Sale Table
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
            
            # 10. Project Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project (
                    project_id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    status VARCHAR(50) DEFAULT 'Active'
                )
            """)

            # 11. Task Table
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
            
            # 12. Messages Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
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
            
            # 13. Notifications Table
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
            
            # 14. Expense Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS expense (
                    expense_id INT AUTO_INCREMENT PRIMARY KEY,
                    category VARCHAR(100),
                    amount DECIMAL(10, 2),
                    date DATE,
                    description TEXT
                )
            """)

            # 15. Audit Log Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    action TEXT,
                    ip_address VARCHAR(45),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # --- SEED DATA ---
            
            # Seed Roles
            cursor.execute("SELECT COUNT(*) as count FROM role")
            if cursor.fetchone()['count'] == 0:
                print("Seeding roles...")
                cursor.execute("INSERT INTO role (role_name) VALUES ('Admin'), ('Manager'), ('Employee')")
            
            # Seed Admin User
            cursor.execute("SELECT COUNT(*) as count FROM users")
            if cursor.fetchone()['count'] == 0:
                print("Seeding admin user...")
                admin_pw = generate_password_hash('admin123')
                cursor.execute(
                    "INSERT INTO users (name, email, password_hash, role_id) VALUES (%s, %s, %s, %s)",
                    ('Administrator', 'admin@erp.com', admin_pw, 1)
                )

        conn.commit()
        conn.close()
        print("✅ Database initialized successfully!")
    except Exception as e:
        print(f"❌ Error during database initialization: {e}")

if __name__ == "__main__":
    init_db()
