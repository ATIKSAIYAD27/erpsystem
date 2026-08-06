import pymysql
import os
from dotenv import load_dotenv

# Load .env file for local development
load_dotenv()

def get_db_connection():
    host = os.environ.get('DB_HOST', os.environ.get('MYSQLHOST', '127.0.0.1'))
    port = int(os.environ.get('DB_PORT', os.environ.get('MYSQLPORT', 3306)))
    user = os.environ.get('DB_USER', os.environ.get('MYSQLUSER', 'root'))
    password = os.environ.get('DB_PASSWORD', os.environ.get('MYSQLPASSWORD', ''))
    database = os.environ.get('DB_NAME', os.environ.get('MYSQLDATABASE', 'erpsystem'))
    
    try:
        return pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5
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
                connect_timeout=5
            )
        except:
            raise primary_error

def migrate_db():
    print("Starting Nexus ERP Migration...")
    
    conn = get_db_connection()
    with conn.cursor() as cursor:
        # ─────────────────────────────────────────────
        # STEP 1: Create new tables
        # ─────────────────────────────────────────────
        
        print("\n[1/7] Creating supplier table...")
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
        print("  OK supplier table ready")

        print("\n[2/7] Creating purchase_order table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_order (
                po_id INT AUTO_INCREMENT PRIMARY KEY,
                supplier_id INT,
                total_amount DECIMAL(10,2),
                status VARCHAR(20) DEFAULT 'Pending',
                order_date DATE,
                expected_delivery DATE,
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES supplier(supplier_id),
                FOREIGN KEY (created_by) REFERENCES users(user_id)
            )
        """)
        print("  [OK] purchase_order table ready")

        print("\n[3/7] Creating purchase_order_item table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_order_item (
                item_id INT AUTO_INCREMENT PRIMARY KEY,
                po_id INT,
                product_id INT,
                quantity INT,
                unit_cost DECIMAL(10,2),
                FOREIGN KEY (po_id) REFERENCES purchase_order(po_id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES product(product_id)
            )
        """)
        print("  [OK] purchase_order_item table ready")

        print("\n[4/7] Creating company_settings table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS company_settings (
                id INT PRIMARY KEY DEFAULT 1,
                company_name VARCHAR(200),
                address TEXT,
                phone VARCHAR(20),
                email VARCHAR(100),
                tax_rate DECIMAL(5,2) DEFAULT 0,
                currency VARCHAR(10) DEFAULT 'INR'
            )
        """)
        print("  [OK] company_settings table ready")

        print("\n[5/7] Creating leave_balance table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leave_balance (
                id INT AUTO_INCREMENT PRIMARY KEY,
                emp_id INT,
                leave_type VARCHAR(50),
                total_days INT DEFAULT 0,
                used_days INT DEFAULT 0,
                year INT,
                FOREIGN KEY (emp_id) REFERENCES employee(emp_id) ON DELETE CASCADE
            )
        """)
        print("  [OK] leave_balance table ready")

        # ─────────────────────────────────────────────
        # STEP 2: Alter existing tables
        # ─────────────────────────────────────────────
        
        print("\n[6/7] Altering existing tables...")
        
        # ALTER employee - add phone
        try:
            cursor.execute("ALTER TABLE employee ADD COLUMN phone VARCHAR(20) AFTER department")
            print("  [OK] Added phone column to employee")
        except Exception as e:
            if "Duplicate column" in str(e):
                print("  [SKIP]  employee.phone already exists, skipping")
            else:
                raise

        # ALTER messages - rename id to message_id
        try:
            cursor.execute("ALTER TABLE messages CHANGE COLUMN id message_id INT AUTO_INCREMENT")
            print("  [OK] Renamed messages.id to messages.message_id")
        except Exception as e:
            if "Unknown column" in str(e) or "Duplicate column" in str(e) or "doesn't exist" in str(e):
                print("  [SKIP] messages.message_id already correct, skipping")
            else:
                raise

        # ALTER expense - add created_by
        try:
            cursor.execute("ALTER TABLE expense ADD COLUMN created_by INT AFTER description")
            print("  [OK] Added created_by column to expense")
        except Exception as e:
            if "Duplicate column" in str(e):
                print("  [SKIP]  expense.created_by already exists, skipping")
            else:
                raise

        # ALTER purchase_order - add expected_delivery
        try:
            cursor.execute("ALTER TABLE purchase_order ADD COLUMN expected_delivery DATE AFTER order_date")
            print("  [OK] Added expected_delivery column to purchase_order")
        except Exception as e:
            if "Duplicate column" in str(e):
                print("  [SKIP]  purchase_order.expected_delivery already exists, skipping")
            else:
                raise

        # ─────────────────────────────────────────────
        # STEP 3: Seed data
        # ─────────────────────────────────────────────
        
        print("\n[7/7] Seeding new data...")
        
        # Seed company_settings
        cursor.execute("SELECT COUNT(*) as count FROM company_settings")
        if cursor.fetchone()['count'] == 0:
            cursor.execute("""
                INSERT INTO company_settings (id, company_name, address)
                VALUES (1, 'Nexus ERP', '123 Business Avenue, Tech City, India')
            """)
            print("  [OK] Seeded company_settings with default row")
        else:
            print("  [SKIP]  company_settings already populated, skipping")

        # Seed leave_balance for all existing employees
        cursor.execute("SELECT emp_id FROM employee")
        employees = cursor.fetchall()
        leave_types = ['Sick', 'Casual', 'Vacation']
        year = 2026
        seeded = 0
        for emp in employees:
            for lt in leave_types:
                cursor.execute("""
                    SELECT COUNT(*) as count FROM leave_balance
                    WHERE emp_id = %s AND leave_type = %s AND year = %s
                """, (emp['emp_id'], lt, year))
                if cursor.fetchone()['count'] == 0:
                    cursor.execute("""
                        INSERT INTO leave_balance (emp_id, leave_type, total_days, used_days, year)
                        VALUES (%s, %s, 12, 0, %s)
                    """, (emp['emp_id'], lt, year))
                    seeded += 1
        print(f"  [OK] Seeded leave_balance for {len(employees)} employees ({seeded} records)")

    conn.commit()
    conn.close()
    print("\nMigration completed successfully!")

if __name__ == "__main__":
    migrate_db()
