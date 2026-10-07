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


def sample_workflow_payload():
    return {
        "name": "Lead Generation Pipeline",
        "description": "Appends new sheets row to CRM lead",
        "definition": {
            "trigger": {
                "connector": "google_sheets",
                "event": "new_row",
                "config": {"spreadsheet_id": "sheet_123"},
            },
            "steps": [
                {
                    "id": "create-lead",
                    "type": "action",
                    "connector": "crm",
                    "action": "create_lead",
                    "config": {},
                    "mapping": {
                        "name": "trigger.values.Name",
                        "email": "trigger.values.Email",
                    },
                }
            ],
        },
    }


def test_publish_workflow_success_and_lifecycle(client):
    headers = register_and_login(client, "Lead Admin", "admin@pipeline.com")
    client.post("/organizations", json={"name": "Pipeline Org"}, headers=headers)

    # 1. Connect Google Sheets and CRM as active connections
    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Pipeline Sheet",
            "config": {"spreadsheet_id": "sheet_123"},
            "credentials": {"client_id": "svc@google.com", "client_secret": "sec_123"},
        },
        headers=headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Pipeline CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "pat_123"},
        },
        headers=headers,
    )

    # 2. Create workflow (Draft V1)
    wf_resp = client.post("/workflows", json=sample_workflow_payload(), headers=headers)
    assert wf_resp.status_code == 201
    wf = wf_resp.json()
    wf_id = wf["id"]
    assert wf["status"] == "draft"
    assert wf["version_number"] == 1
    assert len(wf["versions"]) == 1
    assert wf["versions"][0]["published_at"] is None
    assert wf["versions"][0]["is_active"] is False

    # 3. Publish V1
    pub_resp = client.post(f"/workflows/{wf_id}/publish", headers=headers)
    assert pub_resp.status_code == 200
    pub_wf = pub_resp.json()
    assert pub_wf["status"] == "published"
    assert pub_wf["version_number"] == 1
    assert pub_wf["versions"][0]["published_at"] is not None
    assert pub_wf["versions"][0]["is_active"] is True

    # 4. Calling publish on already published workflow returns 400
    already_pub = client.post(f"/workflows/{wf_id}/publish", headers=headers)
    assert already_pub.status_code == 400
    assert "already published" in already_pub.json()["detail"].lower()

    # 5. Pause workflow
    pause_resp = client.post(f"/workflows/{wf_id}/pause", headers=headers)
    assert pause_resp.status_code == 200
    paused_wf = pause_resp.json()
    assert paused_wf["status"] == "paused"
    assert paused_wf["versions"][0]["published_at"] is not None  # preserved
    assert paused_wf["versions"][0]["is_active"] is False        # inactive while paused

    # 6. Re-publishing a paused workflow restores status = published
    resume_resp = client.post(f"/workflows/{wf_id}/publish", headers=headers)
    assert resume_resp.status_code == 200
    resumed_wf = resume_resp.json()
    assert resumed_wf["status"] == "published"
    assert resumed_wf["versions"][0]["is_active"] is True


def test_publish_workflow_fails_when_connector_not_connected(client):
    headers = register_and_login(client, "Missing Admin", "missing@pipeline.com")
    client.post("/organizations", json={"name": "Missing Org"}, headers=headers)

    # Only connect Google Sheets, but leave CRM unconnected
    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Solo Sheet",
            "config": {"spreadsheet_id": "sheet_solo"},
            "credentials": {"client_id": "svc@google.com", "client_secret": "sec_solo"},
        },
        headers=headers,
    )

    wf_resp = client.post("/workflows", json=sample_workflow_payload(), headers=headers)
    wf_id = wf_resp.json()["id"]

    # Attempt to publish -> fails because CRM has no active connection
    pub_resp = client.post(f"/workflows/{wf_id}/publish", headers=headers)
    assert pub_resp.status_code == 400
    detail = pub_resp.json()["detail"]
    assert "crm" in detail
    assert "active connection" in detail.lower()

    # Workflow must remain draft and unpublished
    get_wf = client.get(f"/workflows/{wf_id}", headers=headers).json()
    assert get_wf["status"] == "draft"
    assert get_wf["versions"][0]["published_at"] is None


def test_publish_workflow_fails_when_connection_status_is_error(client):
    headers = register_and_login(client, "Error Admin", "error@pipeline.com")
    client.post("/organizations", json={"name": "Error Org"}, headers=headers)

    # Google Sheets connects active
    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Good Sheet",
            "config": {"spreadsheet_id": "sheet_good"},
            "credentials": {"client_id": "svc@google.com", "client_secret": "sec_good"},
        },
        headers=headers,
    )
    # CRM connects with invalid credentials -> status: 'error'
    crm_resp = client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Broken CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "invalid_bad_key"},
        },
        headers=headers,
    )
    assert crm_resp.json()["status"] == "error"

    wf_resp = client.post("/workflows", json=sample_workflow_payload(), headers=headers)
    wf_id = wf_resp.json()["id"]

    # Attempt publish -> fails because CRM is in error status
    pub_resp = client.post(f"/workflows/{wf_id}/publish", headers=headers)
    assert pub_resp.status_code == 400
    assert "crm" in pub_resp.json()["detail"]


def test_pause_workflow_preconditions(client):
    headers = register_and_login(client, "Pause Tester", "pause@tester.com")
    client.post("/organizations", json={"name": "Pause Org"}, headers=headers)

    wf_resp = client.post("/workflows", json=sample_workflow_payload(), headers=headers)
    wf_id = wf_resp.json()["id"]

    # 1. Cannot pause a workflow that is in draft status
    pause_draft = client.post(f"/workflows/{wf_id}/pause", headers=headers)
    assert pause_draft.status_code == 400
    assert "cannot pause" in pause_draft.json()["detail"].lower()

    # Connect Google Sheets and CRM, then publish
    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Pause Sheet",
            "config": {"spreadsheet_id": "sheet_p"},
            "credentials": {"client_id": "svc@google.com", "client_secret": "sec_p"},
        },
        headers=headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Pause CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "pat_p"},
        },
        headers=headers,
    )
    client.post(f"/workflows/{wf_id}/publish", headers=headers)

    # 2. Pause published workflow -> succeeds
    pause_pub = client.post(f"/workflows/{wf_id}/pause", headers=headers)
    assert pause_pub.status_code == 200
    assert pause_pub.json()["status"] == "paused"

    # 3. Cannot pause already paused workflow
    pause_again = client.post(f"/workflows/{wf_id}/pause", headers=headers)
    assert pause_again.status_code == 400
    assert "cannot pause" in pause_again.json()["detail"].lower()


def test_version_progression_and_single_active_version_invariant(client):
    headers = register_and_login(client, "Version Architect", "architect@version.com")
    client.post("/organizations", json={"name": "Version Org"}, headers=headers)

    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Sheet",
            "config": {"spreadsheet_id": "sheet_v"},
            "credentials": {"client_id": "svc@google.com", "client_secret": "sec_v"},
        },
        headers=headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "pat_v"},
        },
        headers=headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "whatsapp",
            "name": "WhatsApp",
            "config": {"phone_number_id": "12345"},
            "credentials": {"access_token": "token_v"},
        },
        headers=headers,
    )

    # 1. Create V1
    wf_resp = client.post("/workflows", json=sample_workflow_payload(), headers=headers)
    wf_id = wf_resp.json()["id"]

    # 2. Publish V1
    pub1 = client.post(f"/workflows/{wf_id}/publish", headers=headers).json()
    assert pub1["status"] == "published"
    assert pub1["version_number"] == 1
    assert pub1["versions"][0]["is_active"] is True
    v1_published_at = pub1["versions"][0]["published_at"]
    assert v1_published_at is not None

    # 3. Edit definition -> Spawns V2 Draft, workflow reverts to draft
    new_def = sample_workflow_payload()["definition"]
    new_def["steps"].append(
        {
            "id": "notify-whatsapp",
            "type": "action",
            "connector": "whatsapp",
            "action": "send_text",
            "mapping": {
                "to_number": "trigger.values.Phone",
                "text": "trigger.values.Name",
            },
        }
    )
    edit_resp = client.put(
        f"/workflows/{wf_id}",
        json={"definition": new_def},
        headers=headers,
    )
    assert edit_resp.status_code == 200
    draft_wf = edit_resp.json()
    assert draft_wf["status"] == "draft"
    assert draft_wf["version_number"] == 2
    assert len(draft_wf["versions"]) == 2

    # In draft status: exactly 0 versions are active
    assert not any(v["is_active"] for v in draft_wf["versions"])

    # Historical V1 published_at is preserved
    v1_summary = next(v for v in draft_wf["versions"] if v["version_number"] == 1)
    assert v1_summary["published_at"] == v1_published_at
    # V2 draft has published_at = None
    v2_summary = next(v for v in draft_wf["versions"] if v["version_number"] == 2)
    assert v2_summary["published_at"] is None

    # 4. Publish V2
    pub2 = client.post(f"/workflows/{wf_id}/publish", headers=headers).json()
    assert pub2["status"] == "published"
    assert pub2["version_number"] == 2

    # Invariant: Published active versions <= 1
    active_versions = [v for v in pub2["versions"] if v["is_active"]]
    assert len(active_versions) == 1
    assert active_versions[0]["version_number"] == 2

    # Historical V1 is NOT deleted
    assert len(pub2["versions"]) == 2
    v1_after = next(v for v in pub2["versions"] if v["version_number"] == 1)
    assert v1_after["is_active"] is False
    assert v1_after["published_at"] == v1_published_at


def test_viewer_rbac_for_publish_and_pause(client):
    admin_headers = register_and_login(client, "Lead Admin", "admin@rbac.com")
    client.post("/organizations", json={"name": "RBAC Org"}, headers=admin_headers)

    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "RBAC Sheet",
            "config": {"spreadsheet_id": "sheet_rbac"},
            "credentials": {"client_id": "svc@google.com", "client_secret": "sec_rbac"},
        },
        headers=admin_headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "RBAC CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "pat_rbac"},
        },
        headers=admin_headers,
    )

    wf_resp = client.post("/workflows", json=sample_workflow_payload(), headers=admin_headers)
    wf_id = wf_resp.json()["id"]

    # Invite user as Viewer
    inv_resp = client.post(
        "/organizations/invitations",
        json={"email": "viewer@rbac.com", "role": "Viewer"},
        headers=admin_headers,
    )
    token = inv_resp.json()["token"]

    viewer_headers = register_and_login(client, "Viewer User", "viewer@rbac.com")
    client.post("/organizations/invitations/accept", json={"token": token}, headers=viewer_headers)

    # Viewer CANNOT publish
    unauth_pub = client.post(f"/workflows/{wf_id}/publish", headers=viewer_headers)
    assert unauth_pub.status_code == 403

    # Admin publishes
    client.post(f"/workflows/{wf_id}/publish", headers=admin_headers)

    # Viewer CANNOT pause
    unauth_pause = client.post(f"/workflows/{wf_id}/pause", headers=viewer_headers)
    assert unauth_pause.status_code == 403


def test_publish_pause_organization_isolation(client):
    org_a_headers = register_and_login(client, "User A", "usera@tenant.com")
    client.post("/organizations", json={"name": "Tenant A"}, headers=org_a_headers)

    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "A Sheet",
            "config": {"spreadsheet_id": "sheet_a"},
            "credentials": {"client_id": "svc@google.com", "client_secret": "sec_a"},
        },
        headers=org_a_headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "A CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "pat_a"},
        },
        headers=org_a_headers,
    )

    wf_a = client.post("/workflows", json=sample_workflow_payload(), headers=org_a_headers).json()
    wf_a_id = wf_a["id"]

    # Org B user
    org_b_headers = register_and_login(client, "User B", "userb@tenant.com")
    client.post("/organizations", json={"name": "Tenant B"}, headers=org_b_headers)

    # Org B user cannot publish Org A's workflow
    pub_cross = client.post(f"/workflows/{wf_a_id}/publish", headers=org_b_headers)
    assert pub_cross.status_code == 404

    # Org A publishes
    client.post(f"/workflows/{wf_a_id}/publish", headers=org_a_headers)

    # Org B user cannot pause Org A's workflow
    pause_cross = client.post(f"/workflows/{wf_a_id}/pause", headers=org_b_headers)
    assert pause_cross.status_code == 404
