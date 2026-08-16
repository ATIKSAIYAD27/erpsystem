import pytest
import os
os.environ['SECRET_KEY'] = 'test-secret-key-for-testing-only'
os.environ['DB_HOST'] = '127.0.0.1'
os.environ['DB_NAME'] = 'erpsystem_test'

import sys
import importlib.util

# Import the Flask app from app.py (not the app/ package)
_app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app.py')
_spec = importlib.util.spec_from_file_location("app_module", _app_path)
_app_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_app_module)
flask_app = _app_module.app

@pytest.fixture
def app():
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def auth_client(client):
    """Client logged in as Admin"""
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['role_id'] = 1
        sess['name'] = 'Test Admin'
        sess['role_name'] = 'Admin'
    return client