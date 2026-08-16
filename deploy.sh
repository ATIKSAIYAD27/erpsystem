#!/bin/bash

echo "=== Nexus ERP Deployment ==="

# Wait for MySQL to be ready
echo "Waiting for database..."
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  python -c "
import pymysql, os
conn = pymysql.connect(
    host=os.environ.get('DB_HOST', os.environ.get('MYSQLHOST', '127.0.0.1')),
    port=int(os.environ.get('DB_PORT', os.environ.get('MYSQLPORT', 3306))),
    user=os.environ.get('DB_USER', os.environ.get('MYSQLUSER', 'root')),
    password=os.environ.get('DB_PASSWORD', os.environ.get('MYSQLPASSWORD', '')),
    connect_timeout=5
)
conn.close()
print('Database ready!')
" 2>/dev/null && break
  echo "Attempt $i: Database not ready, waiting 5s..."
  sleep 5
done

# Run database migrations
echo "Running database migrations..."
python init_db.py || echo "init_db.py completed with warnings"
python migrate_performance.py || echo "migrate_performance.py completed with warnings"

# Start with gunicorn using gevent for WebSocket support
echo "Starting server..."
exec gunicorn --config gunicorn_config.py wsgi:app
