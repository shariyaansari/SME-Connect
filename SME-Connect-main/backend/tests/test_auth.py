def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "SME Connect API is running"}


def test_register_user_success(client):
    payload = {
        "name": "Alice Sharma",
        "email": "alice@example.com",
        "password": "Password123!",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Alice Sharma"
    assert data["email"] == "alice@example.com"
    assert data["email_verified"] is False
    assert "id" in data
    assert data["verification_token"] is not None


def test_register_user_duplicate_email(client):
    payload = {
        "name": "Alice Sharma",
        "email": "alice@example.com",
        "password": "Password123!",
    }
    resp1 = client.post("/auth/register", json=payload)
    assert resp1.status_code == 201

    # Same email, different casing
    payload2 = {
        "name": "Alice Duplicate",
        "email": "ALICE@EXAMPLE.COM",
        "password": "Password456!",
    }
    resp2 = client.post("/auth/register", json=payload2)
    assert resp2.status_code == 409
    assert "already registered" in resp2.json()["detail"].lower()


def test_register_invalid_inputs(client):
    # Short password
    res = client.post(
        "/auth/register",
        json={"name": "A", "email": "bad@example.com", "password": "short"},
    )
    assert res.status_code == 422

    # Bad email
    res2 = client.post(
        "/auth/register",
        json={"name": "Valid Name", "email": "not-an-email", "password": "validpassword123"},
    )
    assert res2.status_code == 422


def test_login_success(client):
    register_payload = {
        "name": "Bob Singh",
        "email": "Bob@example.com",
        "password": "SecurePassword123",
    }
    client.post("/auth/register", json=register_payload)

    # Login with lowercase email
    login_payload = {
        "email": "bob@example.com",
        "password": "SecurePassword123",
    }
    response = client.post("/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_credentials(client):
    # Non-existent
    res = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "Password123!"},
    )
    assert res.status_code == 401

    # Wrong password
    client.post(
        "/auth/register",
        json={"name": "Bob", "email": "bob2@example.com", "password": "CorrectPassword1"},
    )
    res2 = client.post(
        "/auth/login",
        json={"email": "bob2@example.com", "password": "WrongPassword1"},
    )
    assert res2.status_code == 401


def test_email_verification(client):
    reg = client.post(
        "/auth/register",
        json={"name": "Charlie", "email": "charlie@example.com", "password": "Password123!"},
    )
    token = reg.json()["verification_token"]

    # Verify email
    verify_resp = client.post("/auth/verify-email", json={"token": token})
    assert verify_resp.status_code == 200
    assert verify_resp.json()["email_verified"] is True

    # Bad token
    bad_resp = client.post("/auth/verify-email", json={"token": "invalid-token-value"})
    assert bad_resp.status_code == 400


def test_refresh_token_lifecycle(client):
    client.post(
        "/auth/register",
        json={"name": "Dave", "email": "dave@example.com", "password": "Password123!"},
    )
    login_resp = client.post(
        "/auth/login",
        json={"email": "dave@example.com", "password": "Password123!"},
    )
    tokens = login_resp.json()
    refresh_token = tokens["refresh_token"]

    # Refresh token
    refresh_resp = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 200
    new_access_token = refresh_resp.json()["access_token"]
    assert new_access_token is not None

    # Test /auth/me with the refreshed token
    me_resp = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "dave@example.com"


def test_get_me_unauthorized(client):
    res = client.get("/auth/me")
    assert res.status_code == 401

    res2 = client.get("/auth/me", headers={"Authorization": "Bearer fake.token.here"})
    assert res2.status_code == 401
