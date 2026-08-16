import multiprocessing
import os

bind = "0.0.0.0:" + os.environ.get("PORT", "8000")
workers = min(multiprocessing.cpu_count() * 2 + 1, 8)

# For WebSocket support (Flask-SocketIO), use gevent or eventlet workers.
# Install: pip install gevent gevent-websocket
# Then set WORKER_CLASS=gevent in .env
worker_class = os.environ.get("WORKER_CLASS", "sync")

if worker_class in ("gevent", "eventlet"):
    worker_connections = 1000
else:
    worker_connections = 1000

timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
accesslog = "gunicorn_access.log"
errorlog = "gunicorn_error.log"
loglevel = "info"
preload_app = True

# Security headers
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190
