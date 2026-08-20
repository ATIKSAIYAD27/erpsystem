#!/usr/bin/env bash
set -e

echo "Initializing database..."
python init_db_pg.py

echo "Running migrations..."
python migrate_performance.py 2>/dev/null || true

echo "Starting Gunicorn..."
exec gunicorn --config gunicorn_config.py wsgi:app
