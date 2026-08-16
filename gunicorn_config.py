import multiprocessing
import os

bind = "0.0.0.0:" + os.environ.get("PORT", "8000")
workers = min(multiprocessing.cpu_count() * 2 + 1, 4)

# Use gevent for WebSocket support (Flask-SocketIO)
worker_class = os.environ.get("WORKER_CLASS", "gevent")

if worker_class in ("gevent", "eventlet"):
    worker_connections = 1000
else:
    worker_connections = 1000

timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
loglevel = "info"
preload_app = True

# Security headers
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190
