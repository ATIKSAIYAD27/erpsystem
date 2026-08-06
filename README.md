# Nexus ERP System

## How to Run on Your PC

### Step 1: Open terminal in project folder

```bash
cd C:\Users\atiks\OneDrive\Documents\erpsystem
```

### Step 2: Activate virtual environment

```bash
venv\Scripts\activate
```

### Step 3: Initialize database (first time only)

```bash
python init_db.py
python migrate_db.py
```

### Step 4: Start the server

```bash
python app.py
```

### Step 5: Open browser and go to

```
http://127.0.0.1:5000
```

### Login

- Email: admin@erp.com
- Password: admin123
