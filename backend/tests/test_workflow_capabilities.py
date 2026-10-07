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


def test_capabilities_contains_all_registered_connectors(client):
    headers = register_and_login(client, "Lead Admin", "admin@capabilities.com")
    client.post("/organizations", json={"name": "Capability Org"}, headers=headers)

    resp = client.get("/workflows/capabilities", headers=headers)
    assert resp.status_code == 200
    capabilities = resp.json()
    assert len(capabilities) >= 6

    slugs = [c["slug"] for c in capabilities]
    assert "google_sheets" in slugs
    assert "crm" in slugs
    assert "stripe" in slugs
    assert "zoho_books" in slugs
    assert "custom_api" in slugs
    assert "whatsapp" in slugs

    for cap in capabilities:
        assert "slug" in cap
        assert "name" in cap
        assert "category" in cap
        assert "description" in cap
        assert "icon" in cap
        assert "is_connected" in cap
        assert isinstance(cap["connections"], list)
        assert isinstance(cap["supported_triggers"], list)
        assert isinstance(cap["supported_actions"], list)


def test_capabilities_exposes_trigger_and_action_schemas(client):
    headers = register_and_login(client, "Schema Tester", "tester@schema.com")
    client.post("/organizations", json={"name": "Schema Org"}, headers=headers)

    resp = client.get("/workflows/capabilities", headers=headers)
    assert resp.status_code == 200
    caps = {c["slug"]: c for c in resp.json()}

    # 1. Google Sheets triggers and actions
    sheets = caps["google_sheets"]
    trigger_slugs = [t["slug"] for t in sheets["supported_triggers"]]
    assert "new_row" in trigger_slugs
    new_row = next(t for t in sheets["supported_triggers"] if t["slug"] == "new_row")
    assert "row_index" in new_row["payload_schema"]
    assert new_row["payload_schema"]["row_index"]["type"] == "number"
    assert "values" in new_row["payload_schema"]
    assert new_row["payload_schema"]["values"]["type"] == "object"
    assert "created_at" in new_row["payload_schema"]

    action_slugs = [a["slug"] for a in sheets["supported_actions"]]
    assert "append_row" in action_slugs
    append_row = next(a for a in sheets["supported_actions"] if a["slug"] == "append_row")
    assert "values" in append_row["input_schema"]
    assert append_row["input_schema"]["values"]["type"] == "object"
    assert append_row["input_schema"]["values"]["required"] is True

    # 2. CRM triggers and actions
    crm = caps["crm"]
    crm_triggers = [t["slug"] for t in crm["supported_triggers"]]
    assert "new_lead" in crm_triggers
    new_lead = next(t for t in crm["supported_triggers"] if t["slug"] == "new_lead")
    assert "lead_id" in new_lead["payload_schema"]
    assert new_lead["payload_schema"]["lead_id"]["type"] == "string"
    assert "name" in new_lead["payload_schema"]
    assert "email" in new_lead["payload_schema"]

    crm_actions = [a["slug"] for a in crm["supported_actions"]]
    assert "create_lead" in crm_actions
    create_lead = next(a for a in crm["supported_actions"] if a["slug"] == "create_lead")
    assert "name" in create_lead["input_schema"]
    assert create_lead["input_schema"]["name"]["required"] is True
    assert create_lead["input_schema"]["name"]["type"] == "string"
    assert "email" in create_lead["input_schema"]
    assert create_lead["input_schema"]["email"]["required"] is True
    assert "phone" in create_lead["input_schema"]
    assert create_lead["input_schema"]["phone"]["required"] is False

    # 3. WhatsApp actions
    whatsapp = caps["whatsapp"]
    send_text = next(a for a in whatsapp["supported_actions"] if a["slug"] == "send_text")
    assert send_text["input_schema"]["to_number"]["required"] is True
    assert send_text["input_schema"]["text"]["required"] is True


def test_capabilities_organization_connection_availability(client):
    headers = register_and_login(client, "Ops Director", "ops@availability.com")
    client.post("/organizations", json={"name": "Availability Org"}, headers=headers)

    # Initial state: no connections
    initial_resp = client.get("/workflows/capabilities", headers=headers)
    assert initial_resp.status_code == 200
    for c in initial_resp.json():
        assert c["is_connected"] is False
        assert len(c["connections"]) == 0

    # Add Google Sheets connection
    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Live Orders Sheet",
            "config": {"spreadsheet_id": "sheet_12345"},
            "credentials": {"client_id": "svc@google.com", "client_secret": "secret_gs_123"},
        },
        headers=headers,
    )

    # Add CRM connection
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Production HubSpot",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "pat-valid-key"},
        },
        headers=headers,
    )

    # Query capabilities again
    updated_resp = client.get("/workflows/capabilities", headers=headers)
    assert updated_resp.status_code == 200
    caps_by_slug = {c["slug"]: c for c in updated_resp.json()}

    assert caps_by_slug["google_sheets"]["is_connected"] is True
    assert len(caps_by_slug["google_sheets"]["connections"]) == 1
    assert caps_by_slug["google_sheets"]["connections"][0]["name"] == "Live Orders Sheet"
    assert caps_by_slug["google_sheets"]["connections"][0]["status"] == "active"

    assert caps_by_slug["crm"]["is_connected"] is True
    assert len(caps_by_slug["crm"]["connections"]) == 1
    assert caps_by_slug["crm"]["connections"][0]["name"] == "Production HubSpot"

    assert caps_by_slug["stripe"]["is_connected"] is False
    assert len(caps_by_slug["stripe"]["connections"]) == 0


def test_capabilities_organization_isolation(client):
    # Org A connects Google Sheets
    org_a_headers = register_and_login(client, "Admin A", "admin_a@tenant.com")
    client.post("/organizations", json={"name": "Org A Tenant"}, headers=org_a_headers)

    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Org A Secret Sheet",
            "config": {"spreadsheet_id": "sheet_tenant_a"},
            "credentials": {"client_id": "svc_a@google.com", "client_secret": "secret_a_123"},
        },
        headers=org_a_headers,
    )

    # Org B user creates separate organization
    org_b_headers = register_and_login(client, "Admin B", "admin_b@tenant.com")
    client.post("/organizations", json={"name": "Org B Tenant"}, headers=org_b_headers)

    # Org B queries capabilities
    org_b_resp = client.get("/workflows/capabilities", headers=org_b_headers)
    assert org_b_resp.status_code == 200
    org_b_caps = {c["slug"]: c for c in org_b_resp.json()}

    # Org B must NOT see Org A's Google Sheets connection
    assert org_b_caps["google_sheets"]["is_connected"] is False
    assert len(org_b_caps["google_sheets"]["connections"]) == 0


def test_capabilities_never_exposes_credentials(client):
    headers = register_and_login(client, "Security Officer", "security@vault.com")
    client.post("/organizations", json={"name": "Vault Org"}, headers=headers)

    secret_key = "super_classified_api_token_xyz_987654"
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Secure CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": secret_key},
        },
        headers=headers,
    )

    resp = client.get("/workflows/capabilities", headers=headers)
    assert resp.status_code == 200
    raw_response_text = resp.text

    # Raw secret must NEVER appear anywhere in the capabilities response
    assert secret_key not in raw_response_text
    assert "_encrypted" not in raw_response_text

    # Connection items must only have safe metadata (id, name, status, created_at, last_tested_at)
    for cap in resp.json():
        for conn in cap["connections"]:
            assert "credentials" not in conn
            assert "masked_credentials" not in conn
            assert "config" not in conn


def test_single_connector_capability_endpoint(client):
    headers = register_and_login(client, "Single Inspector", "single@inspect.com")
    client.post("/organizations", json={"name": "Inspect Org"}, headers=headers)

    # Fetch specific connector
    resp = client.get("/workflows/capabilities/google_sheets", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == "google_sheets"
    assert data["name"] == "Google Sheets"
    assert len(data["supported_triggers"]) > 0
    assert len(data["supported_actions"]) > 0

    # Fetch unknown connector returns 404
    bad_resp = client.get("/workflows/capabilities/unknown_external_service", headers=headers)
    assert bad_resp.status_code == 404
    assert "unknown connector slug" in bad_resp.json()["detail"].lower()


def test_capabilities_viewer_can_read(client):
    admin_headers = register_and_login(client, "Admin Lead", "admin@rolecheck.com")
    client.post("/organizations", json={"name": "Role Org"}, headers=admin_headers)

    # Add a connection as Admin
    client.post(
        "/connectors",
        json={
            "connector_slug": "whatsapp",
            "name": "Support WhatsApp",
            "config": {"phone_number_id": "11223344"},
            "credentials": {"access_token": "token_abc123"},
        },
        headers=admin_headers,
    )

    # Invite user as Viewer
    inv_resp = client.post(
        "/organizations/invitations",
        json={"email": "viewer@rolecheck.com", "role": "Viewer"},
        headers=admin_headers,
    )
    token = inv_resp.json()["token"]

    viewer_headers = register_and_login(client, "Viewer User", "viewer@rolecheck.com")
    client.post("/organizations/invitations/accept", json={"token": token}, headers=viewer_headers)

    # Viewer can read capabilities and sees configured connections
    viewer_resp = client.get("/workflows/capabilities", headers=viewer_headers)
    assert viewer_resp.status_code == 200
    caps = {c["slug"]: c for c in viewer_resp.json()}
    assert caps["whatsapp"]["is_connected"] is True
    assert len(caps["whatsapp"]["connections"]) == 1


def test_capabilities_unauthorized_when_not_logged_in(client):
    resp = client.get("/workflows/capabilities")
    assert resp.status_code == 401
