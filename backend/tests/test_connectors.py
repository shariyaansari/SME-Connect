def register_and_login(client, name: str, email: str, password: str = "Password123!") -> dict:
    client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    login_resp = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    access_token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


def test_get_connectors_catalog(client):
    response = client.get("/connectors/catalog")
    assert response.status_code == 200
    catalog = response.json()
    assert len(catalog) >= 4
    slugs = [item["slug"] for item in catalog]
    assert "google_sheets" in slugs
    assert "crm" in slugs
    assert "custom_api" in slugs
    assert "whatsapp" in slugs

    # Validate structure of a catalog item
    sheets_item = next(item for item in catalog if item["slug"] == "google_sheets")
    assert sheets_item["name"] == "Google Sheets"
    assert sheets_item["category"] == "Spreadsheets"
    assert len(sheets_item["config_fields"]) > 0
    assert len(sheets_item["credential_fields"]) > 0
    assert len(sheets_item["supported_triggers"]) > 0
    assert len(sheets_item["supported_actions"]) > 0


def test_create_connection_success_and_masking(client):
    headers = register_and_login(client, "Lead Admin", "admin@leads.com")
    client.post("/organizations", json={"name": "Sales Workspace"}, headers=headers)

    payload = {
        "connector_slug": "google_sheets",
        "name": "Customer Orders Sheet",
        "auth_type": "oauth2",
        "config": {
            "spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
            "sheet_name": "Orders",
        },
        "credentials": {
            "client_id": "svc@project.iam.gserviceaccount.com",
            "client_secret": "super_secret_google_key_987654321",
        },
    }

    create_resp = client.post("/connectors", json=payload, headers=headers)
    assert create_resp.status_code == 201
    conn = create_resp.json()
    assert conn["name"] == "Customer Orders Sheet"
    assert conn["connector_slug"] == "google_sheets"
    assert conn["status"] == "active"
    assert conn["last_tested_at"] is not None
    assert conn["error_message"] is None

    # Verify credentials are strictly masked
    masked = conn["masked_credentials"]
    assert "super_secret_google_key_987654321" not in str(masked)
    assert "••••" in masked["client_secret"]


def test_create_connection_invalid_slug(client):
    headers = register_and_login(client, "Dev Admin", "dev@org.com")
    client.post("/organizations", json={"name": "Dev Org"}, headers=headers)

    payload = {
        "connector_slug": "non_existent_app",
        "name": "Invalid App",
        "config": {},
        "credentials": {},
    }
    response = client.post("/connectors", json=payload, headers=headers)
    assert response.status_code == 400
    assert "unknown connector slug" in response.json()["detail"].lower()


def test_create_connection_failed_health_check(client):
    headers = register_and_login(client, "Tester", "tester@org.com")
    client.post("/organizations", json={"name": "Test Org"}, headers=headers)

    payload = {
        "connector_slug": "crm",
        "name": "Broken CRM",
        "config": {"crm_provider": "HubSpot"},
        "credentials": {"api_key": "invalid_api_token"},
    }
    response = client.post("/connectors", json=payload, headers=headers)
    assert response.status_code == 201
    conn = response.json()
    assert conn["status"] == "error"
    assert conn["error_message"] is not None
    assert "invalid token" in conn["error_message"].lower()


def test_list_and_get_connections(client):
    headers = register_and_login(client, "Manager", "manager@org.com")
    client.post("/organizations", json={"name": "Ops Org"}, headers=headers)

    # Create 2 connections
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Main CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "valid_hubspot_key_12345"},
        },
        headers=headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "custom_api",
            "name": "Webhook API",
            "config": {"base_url": "https://api.internal-erp.com/v1"},
            "credentials": {"auth_header_value": "Bearer token123"},
        },
        headers=headers,
    )

    list_resp = client.get("/connectors", headers=headers)
    assert list_resp.status_code == 200
    conns = list_resp.json()
    assert len(conns) == 2

    # Get single connection
    first_id = conns[0]["id"]
    get_resp = client.get(f"/connectors/{first_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == first_id


def test_test_connection_endpoint(client):
    headers = register_and_login(client, "Engineer", "eng@org.com")
    client.post("/organizations", json={"name": "Eng Org"}, headers=headers)

    create_resp = client.post(
        "/connectors",
        json={
            "connector_slug": "custom_api",
            "name": "API Service",
            "config": {"base_url": "https://api.test.com"},
            "credentials": {},
        },
        headers=headers,
    )
    conn_id = create_resp.json()["id"]

    # Trigger test
    test_resp = client.post(f"/connectors/{conn_id}/test", headers=headers)
    assert test_resp.status_code == 200
    result = test_resp.json()
    assert result["success"] is True
    assert result["status"] == "active"
    assert "https://api.test.com" in result["message"]


def test_update_and_delete_connection(client):
    headers = register_and_login(client, "Admin", "admin@manage.com")
    client.post("/organizations", json={"name": "Manage Org"}, headers=headers)

    create_resp = client.post(
        "/connectors",
        json={
            "connector_slug": "whatsapp",
            "name": "WhatsApp Notifications",
            "config": {"phone_number_id": "12345678"},
            "credentials": {"access_token": "valid_token_abc"},
        },
        headers=headers,
    )
    conn_id = create_resp.json()["id"]

    # Update name and config
    update_resp = client.put(
        f"/connectors/{conn_id}",
        json={
            "name": "WhatsApp Alert Center",
            "config": {"phone_number_id": "87654321"},
        },
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "WhatsApp Alert Center"
    assert update_resp.json()["config"]["phone_number_id"] == "87654321"

    # Delete connection
    del_resp = client.delete(f"/connectors/{conn_id}", headers=headers)
    assert del_resp.status_code == 204

    # Verify 404 after deletion
    get_del = client.get(f"/connectors/{conn_id}", headers=headers)
    assert get_del.status_code == 404


def test_viewer_cannot_mutate_connections(client):
    admin_headers = register_and_login(client, "Lead Admin", "admin@secure.com")
    client.post("/organizations", json={"name": "Secure Org"}, headers=admin_headers)

    create_resp = client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Production CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "prod_key_123"},
        },
        headers=admin_headers,
    )
    conn_id = create_resp.json()["id"]

    # Invite user as Viewer
    invite_resp = client.post(
        "/organizations/invitations",
        json={"email": "viewer@secure.com", "role": "Viewer"},
        headers=admin_headers,
    )
    token = invite_resp.json()["token"]

    viewer_headers = register_and_login(client, "Auditor Viewer", "viewer@secure.com")
    client.post("/organizations/invitations/accept", json={"token": token}, headers=viewer_headers)

    # Viewer CAN read
    view_list = client.get("/connectors", headers=viewer_headers)
    assert view_list.status_code == 200
    assert len(view_list.json()) == 1

    # Viewer CANNOT create
    unauth_create = client.post(
        "/connectors",
        json={
            "connector_slug": "custom_api",
            "name": "Unauthorized API",
            "config": {"base_url": "https://hack.com"},
            "credentials": {},
        },
        headers=viewer_headers,
    )
    assert unauth_create.status_code == 403

    # Viewer CANNOT test
    unauth_test = client.post(f"/connectors/{conn_id}/test", headers=viewer_headers)
    assert unauth_test.status_code == 403

    # Viewer CANNOT update
    unauth_update = client.put(
        f"/connectors/{conn_id}",
        json={"name": "Hacked Name"},
        headers=viewer_headers,
    )
    assert unauth_update.status_code == 403

    # Viewer CANNOT delete
    unauth_del = client.delete(f"/connectors/{conn_id}", headers=viewer_headers)
    assert unauth_del.status_code == 403


def test_organization_isolation(client):
    # Org A creates a connection
    org_a_headers = register_and_login(client, "User A", "user_a@orga.com")
    client.post("/organizations", json={"name": "Org A"}, headers=org_a_headers)

    conn_a_resp = client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Org A CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "orga_key_123"},
        },
        headers=org_a_headers,
    )
    conn_a_id = conn_a_resp.json()["id"]

    # Org B user
    org_b_headers = register_and_login(client, "User B", "user_b@orgb.com")
    client.post("/organizations", json={"name": "Org B"}, headers=org_b_headers)

    # Org B user cannot see Org A connection in list
    org_b_list = client.get("/connectors", headers=org_b_headers).json()
    assert len(org_b_list) == 0

    # Org B user cannot fetch Org A connection
    org_b_get = client.get(f"/connectors/{conn_a_id}", headers=org_b_headers)
    assert org_b_get.status_code == 404

    # Org B user cannot delete Org A connection
    org_b_del = client.delete(f"/connectors/{conn_a_id}", headers=org_b_headers)
    assert org_b_del.status_code == 404
