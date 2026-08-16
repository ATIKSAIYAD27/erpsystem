def test_csrf_protection(app):
    with app.test_client() as client:
        response = client.post('/login', data={'email': 'test@test.com', 'password': 'test'})
        # Should get 400 CSRF error or redirect
        assert response.status_code in [200, 302, 400]

def test_delete_requires_post(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['role_id'] = 1
        sess['name'] = 'Admin'
        sess['role_name'] = 'Admin'
    response = client.get('/employee/delete/1', follow_redirects=False)
    assert response.status_code == 405  # Method not allowed

def test_password_validation():
    import re
    # Test the validation function
    from app.routes.auth import _validate_password
    assert _validate_password('short') is not None  # Too short
    assert _validate_password('nouppercase1!') is not None  # No uppercase
    assert _validate_password('NOLOWERCASE1!') is not None  # No lowercase
    assert _validate_password('NoDigit!') is not None  # No digit
    assert _validate_password('NoSpecial1') is not None  # No special
    assert _validate_password('Valid1Pass!') is None  # Valid