import psycopg2
import os
from werkzeug.security import generate_password_hash


def get_db_connection():
    return psycopg2.connect(
        host=os.environ['DB_HOST'],
        port=int(os.environ.get('DB_PORT', 5432)),
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'],
        database=os.environ['DB_NAME'],
        sslmode='require',
    )


def init_db():
    print("Initializing Nexus ERP Database (PostgreSQL)...")

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS role (
                role_id SERIAL PRIMARY KEY,
                role_name VARCHAR(50) NOT NULL UNIQUE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS employee (
                emp_id SERIAL PRIMARY KEY,
                user_id INT,
                job_title VARCHAR(100),
                department VARCHAR(100),
                phone VARCHAR(20),
                salary DECIMAL(10, 2),
                hire_date DATE,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                attendance_id SERIAL PRIMARY KEY,
                emp_id INT,
                date DATE,
                status VARCHAR(20),
                check_in TIME,
                check_out TIME,
                FOREIGN KEY (emp_id) REFERENCES employee(emp_id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS leaves (
                leave_id SERIAL PRIMARY KEY,
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS leave_balance (
                id SERIAL PRIMARY KEY,
                emp_id INT,
                leave_type VARCHAR(50),
                total_days INT DEFAULT 12,
                used_days INT DEFAULT 0,
                year INT,
                FOREIGN KEY (emp_id) REFERENCES employee(emp_id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS payroll (
                payroll_id SERIAL PRIMARY KEY,
                emp_id INT,
                month INT,
                year INT,
                basic DECIMAL(10, 2),
                deductions DECIMAL(10, 2) DEFAULT 0,
                net_pay DECIMAL(10, 2),
                FOREIGN KEY (emp_id) REFERENCES employee(emp_id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS customer (
                customer_id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100),
                phone VARCHAR(20),
                address TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS product (
                product_id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                sku VARCHAR(50) UNIQUE,
                description TEXT,
                unit_price DECIMAL(10, 2),
                quantity INT DEFAULT 0,
                reorder_level INT DEFAULT 10
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sale (
                sale_id SERIAL PRIMARY KEY,
                customer_id INT,
                product_id INT,
                quantity INT,
                total_amount DECIMAL(10, 2),
                sale_date DATE,
                FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
                FOREIGN KEY (product_id) REFERENCES product(product_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS project (
                project_id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                status VARCHAR(50) DEFAULT 'Active'
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS task (
                task_id SERIAL PRIMARY KEY,
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id SERIAL PRIMARY KEY,
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                user_id INT,
                message TEXT NOT NULL,
                type VARCHAR(20) DEFAULT 'info',
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS expense (
                expense_id SERIAL PRIMARY KEY,
                category VARCHAR(100),
                department VARCHAR(100) DEFAULT 'General',
                amount DECIMAL(10, 2),
                date DATE,
                description TEXT,
                created_by INT,
                FOREIGN KEY (created_by) REFERENCES users(user_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                user_id INT,
                action TEXT,
                ip_address VARCHAR(45),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS supplier (
                supplier_id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100),
                phone VARCHAR(20),
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS purchase_order (
                po_id SERIAL PRIMARY KEY,
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS purchase_order_item (
                item_id SERIAL PRIMARY KEY,
                po_id INT,
                product_id INT,
                quantity INT,
                unit_cost DECIMAL(10, 2),
                FOREIGN KEY (po_id) REFERENCES purchase_order(po_id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES product(product_id)
            )
        """)

        cur.execute("""
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS document (
                doc_id SERIAL PRIMARY KEY,
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS quotation (
                quote_id SERIAL PRIMARY KEY,
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS quotation_item (
                item_id SERIAL PRIMARY KEY,
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS calendar_event (
                event_id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE,
                event_type VARCHAR(50) DEFAULT 'event',
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(user_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS budget (
                budget_id SERIAL PRIMARY KEY,
                department VARCHAR(100) NOT NULL,
                allocated_amount DECIMAL(12, 2) DEFAULT 0,
                fiscal_year INT NOT NULL,
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (department, fiscal_year),
                FOREIGN KEY (created_by) REFERENCES users(user_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS workflow (
                workflow_id SERIAL PRIMARY KEY,
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS workflow_request (
                request_id SERIAL PRIMARY KEY,
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS risk (
                risk_id SERIAL PRIMARY KEY,
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sales_pipeline (
                deal_id SERIAL PRIMARY KEY,
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sales_target (
                target_id SERIAL PRIMARY KEY,
                month INT NOT NULL,
                year INT NOT NULL,
                target_amount DECIMAL(12, 2) DEFAULT 0,
                set_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (month, year),
                FOREIGN KEY (set_by) REFERENCES users(user_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS document_share (
                id SERIAL PRIMARY KEY,
                doc_id INT,
                user_id INT,
                shared_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (doc_id) REFERENCES document(doc_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (shared_by) REFERENCES users(user_id),
                UNIQUE (doc_id, user_id)
            )
        """)

        cur.execute("SELECT COUNT(*) as count FROM role")
        if cur.fetchone()[0] == 0:
            print("Seeding roles...")
            cur.execute("INSERT INTO role (role_name) VALUES ('Admin'), ('Manager'), ('Employee')")

        cur.execute("SELECT COUNT(*) as count FROM users")
        if cur.fetchone()[0] == 0:
            print("Seeding admin user...")
            admin_pw = generate_password_hash('admin123')
            cur.execute(
                "INSERT INTO users (name, email, password_hash, role_id) VALUES (%s, %s, %s, %s)",
                ('Administrator', 'admin@nexus-erp.in', admin_pw, 1)
            )

    conn.commit()
    conn.close()
    print("Database initialized successfully!")


if __name__ == "__main__":
    init_db()
