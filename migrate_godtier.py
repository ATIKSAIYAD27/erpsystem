import pymysql
import os
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    host = os.environ.get('DB_HOST', os.environ.get('MYSQLHOST', '127.0.0.1'))
    port = int(os.environ.get('DB_PORT', os.environ.get('MYSQLPORT', 3306)))
    user = os.environ.get('DB_USER', os.environ.get('MYSQLUSER', 'root'))
    password = os.environ.get('DB_PASSWORD', os.environ.get('MYSQLPASSWORD', ''))
    database = os.environ.get('DB_NAME', os.environ.get('MYSQLDATABASE', 'erpsystem'))
    return pymysql.connect(
        host=host, port=port, user=user, password=password,
        database=database, cursorclass=pymysql.cursors.DictCursor, connect_timeout=5
    )


def migrate():
    print("Running migration: Adding God Tier features...")

    conn = get_db_connection()
    with conn.cursor() as cursor:

        migrations = [
            ("ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret VARCHAR(64) AFTER password_hash",
             "Added totp_secret column"),
            ("ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_enabled BOOLEAN DEFAULT FALSE AFTER totp_secret",
             "Added totp_enabled column"),
            ("ALTER TABLE users ADD COLUMN IF NOT EXISTS api_token VARCHAR(128) AFTER totp_enabled",
             "Added api_token column"),

            ("""CREATE TABLE IF NOT EXISTS document (
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
            )""", "Created document table"),

            ("""CREATE TABLE IF NOT EXISTS document_share (
                id INT AUTO_INCREMENT PRIMARY KEY,
                doc_id INT,
                user_id INT,
                shared_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (doc_id) REFERENCES document(doc_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (shared_by) REFERENCES users(user_id),
                UNIQUE KEY unique_share (doc_id, user_id)
            )""", "Created document_share table"),

            ("""CREATE TABLE IF NOT EXISTS quotation (
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
            )""", "Created quotation table"),

            ("""CREATE TABLE IF NOT EXISTS quotation_item (
                item_id INT AUTO_INCREMENT PRIMARY KEY,
                quote_id INT,
                product_id INT,
                quantity INT DEFAULT 1,
                unit_price DECIMAL(10, 2) DEFAULT 0,
                discount DECIMAL(10, 2) DEFAULT 0,
                line_total DECIMAL(12, 2) DEFAULT 0,
                FOREIGN KEY (quote_id) REFERENCES quotation(quote_id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES product(product_id)
            )""", "Created quotation_item table"),

            ("""CREATE TABLE IF NOT EXISTS calendar_event (
                event_id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE,
                event_type VARCHAR(50) DEFAULT 'event',
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(user_id)
            )""", "Created calendar_event table"),

            ("""CREATE TABLE IF NOT EXISTS budget (
                budget_id INT AUTO_INCREMENT PRIMARY KEY,
                department VARCHAR(100) NOT NULL,
                allocated_amount DECIMAL(12, 2) DEFAULT 0,
                fiscal_year INT NOT NULL,
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_dept_year (department, fiscal_year),
                FOREIGN KEY (created_by) REFERENCES users(user_id)
            )""", "Created budget table"),

            ("""CREATE TABLE IF NOT EXISTS workflow (
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
            )""", "Created workflow table"),

            ("""CREATE TABLE IF NOT EXISTS workflow_request (
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
            )""", "Created workflow_request table"),

            ("""CREATE TABLE IF NOT EXISTS risk (
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
            )""", "Created risk table"),

            ("""CREATE TABLE IF NOT EXISTS sales_pipeline (
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
            )""", "Created sales_pipeline table"),

            ("""CREATE TABLE IF NOT EXISTS sales_target (
                target_id INT AUTO_INCREMENT PRIMARY KEY,
                month INT NOT NULL,
                year INT NOT NULL,
                target_amount DECIMAL(12, 2) DEFAULT 0,
                set_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_month_year (month, year),
                FOREIGN KEY (set_by) REFERENCES users(user_id)
            )""", "Created sales_target table"),
        ]

        for sql, description in migrations:
            try:
                cursor.execute(sql)
                print(f"  [OK] {description}")
            except Exception as e:
                if "Duplicate column" in str(e):
                    print(f"  [SKIP] {description} (already exists)")
                else:
                    print(f"  [WARN] {description}: {e}")

    conn.commit()
    conn.close()
    print("Migration complete!")


if __name__ == "__main__":
    migrate()
