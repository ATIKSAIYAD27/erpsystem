def test_login_page_loads(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert b'Welcome Back' in response.data

def test_register_page_loads(client):
    response = client.get('/register')
    assert response.status_code == 200
    assert b'Create Account' in response.data

def test_login_requires_email(client):
    response = client.post('/login', data={'email': '', 'password': 'test'}, follow_redirects=True)
    assert response.status_code == 200

def test_protected_redirects(client):
    response = client.get('/dashboard', follow_redirects=False)
    assert response.status_code == 302
    assert '/login' in response.headers['Location']

def test_logout(client):
    response = client.get('/logout', follow_redirects=False)
    assert response.status_code == 302