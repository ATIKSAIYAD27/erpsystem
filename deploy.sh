#!/bin/bash
set -e

echo "=== Nexus ERP Deployment ==="

# Run database migrations
echo "Running database migrations..."
python init_db.py || echo "init_db.py completed with warnings"
python migrate_performance.py || echo "migrate_performance.py completed with warnings"

# Start with gunicorn using gevent for WebSocket support
echo "Starting server..."
gunicorn --config gunicorn_config.py app:app
