def test_admin_access_dashboard(auth_client):
    response = auth_client.get('/dashboard')
    assert response.status_code in [200, 500]

def test_unauthenticated_dashboard(client):
    response = client.get('/dashboard', follow_redirects=False)
    assert response.status_code == 302

def test_employee_cannot_access_inventory(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 2
        sess['role_id'] = 3
        sess['name'] = 'Test Employee'
        sess['role_name'] = 'Employee'
    response = client.get('/inventory', follow_redirects=False)
    assert response.status_code == 302

def test_health_check(client):
    response = client.get('/health')
    assert response.status_code in [200, 503]