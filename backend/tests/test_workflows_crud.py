import pytest
from app.database.models import Workflow, WorkflowVersion


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


SAMPLE_DEFINITION = {
    "trigger": {
        "connector": "google_sheets",
        "event": "new_row",
        "config": {
            "spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
            "sheet_name": "Inquiries",
        },
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
                "phone": "trigger.values.Phone",
            },
        }
    ],
}


def test_create_workflow_success(client, db_session):
    headers = register_and_login(client, "Lead Engineer", "lead@company.com")
    org_resp = client.post("/organizations", json={"name": "Engineering Workspace"}, headers=headers)
    org_id = org_resp.json()["id"]

    create_payload = {
        "name": "Lead Intake Automation",
        "description": "Syncs new row leads into HubSpot CRM",
        "definition": SAMPLE_DEFINITION,
    }

    resp = client.post("/workflows", json=create_payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Lead Intake Automation"
    assert data["description"] == "Syncs new row leads into HubSpot CRM"
    assert data["status"] == "draft"
    assert data["version_number"] == 1
    assert data["organization_id"] == org_id
    assert len(data["versions"]) == 1
    assert data["versions"][0]["version_number"] == 1
    assert data["versions"][0]["published_at"] is None

    # Verify persistence in database
    db_wf = db_session.get(Workflow, data["id"])
    assert db_wf is not None
    assert db_wf.name == "Lead Intake Automation"

    db_ver = db_session.query(WorkflowVersion).filter_by(workflow_id=data["id"]).first()
    assert db_ver is not None
    assert db_ver.version_number == 1
    assert db_ver.definition["trigger"]["connector"] == "google_sheets"


def test_create_workflow_validation_failure(client):
    headers = register_and_login(client, "Admin User", "admin@flows.com")
    client.post("/organizations", json={"name": "Flows Org"}, headers=headers)

    invalid_payload = {
        "name": "Broken Workflow",
        "definition": {
            "trigger": {
                "connector": "non_existent_app",  # Invalid connector
                "event": "new_row",
            },
            "steps": [
                {
                    "id": "step-1",
                    "type": "action",
                    "connector": "crm",
                    "action": "create_lead",
                }
            ],
        },
    }

    resp = client.post("/workflows", json=invalid_payload, headers=headers)
    assert resp.status_code == 422
    errors = resp.json()["detail"]
    assert any("UNKNOWN_CONNECTOR" in e.get("code", "") for e in errors)


def test_list_and_get_workflows(client):
    headers = register_and_login(client, "Manager", "manager@team.com")
    org_resp = client.post("/organizations", json={"name": "Ops Team"}, headers=headers)
    org_id = org_resp.json()["id"]

    # Initially empty
    list_resp = client.get("/workflows", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json() == []

    # Create two workflows
    wf1 = client.post(
        "/workflows",
        json={"name": "Flow Alpha", "definition": SAMPLE_DEFINITION},
        headers=headers,
    ).json()

    wf2 = client.post(
        "/workflows",
        json={"name": "Flow Beta", "definition": SAMPLE_DEFINITION},
        headers=headers,
    ).json()

    list_resp = client.get("/workflows", headers=headers)
    assert list_resp.status_code == 200
    flows = list_resp.json()
    assert len(flows) == 2
    names = [f["name"] for f in flows]
    assert "Flow Alpha" in names
    assert "Flow Beta" in names

    # Filter by status
    drafts_resp = client.get("/workflows?status=draft", headers=headers)
    assert len(drafts_resp.json()) == 2

    # Get single workflow
    get_resp = client.get(f"/workflows/{wf1['id']}", headers=headers)
    assert get_resp.status_code == 200
    detail = get_resp.json()
    assert detail["id"] == wf1["id"]
    assert detail["name"] == "Flow Alpha"
    assert detail["definition"]["trigger"]["connector"] == "google_sheets"


def test_update_workflow_name_and_definition(client):
    headers = register_and_login(client, "Editor User", "editor@dev.com")
    client.post("/organizations", json={"name": "Dev Org"}, headers=headers)

    created = client.post(
        "/workflows",
        json={"name": "Initial Name", "definition": SAMPLE_DEFINITION},
        headers=headers,
    ).json()
    wf_id = created["id"]

    updated_definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
            "config": {"sheet_name": "UpdatedSheet"},
        },
        "steps": [
            {
                "id": "create-lead",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "mapping": {"email": "trigger.values.Email"},
            }
        ],
    }

    update_payload = {
        "name": "Updated Name",
        "description": "Brand new description",
        "definition": updated_definition,
    }

    put_resp = client.put(f"/workflows/{wf_id}", json=update_payload, headers=headers)
    assert put_resp.status_code == 200
    updated_data = put_resp.json()
    assert updated_data["name"] == "Updated Name"
    assert updated_data["description"] == "Brand new description"
    assert updated_data["definition"]["trigger"]["config"]["sheet_name"] == "UpdatedSheet"


def test_delete_workflow(client, db_session):
    headers = register_and_login(client, "Lead Dev", "dev@ops.com")
    client.post("/organizations", json={"name": "Delete Org"}, headers=headers)

    created = client.post(
        "/workflows",
        json={"name": "To Be Deleted", "definition": SAMPLE_DEFINITION},
        headers=headers,
    ).json()
    wf_id = created["id"]

    del_resp = client.delete(f"/workflows/{wf_id}", headers=headers)
    assert del_resp.status_code == 204

    # Subsequent GET returns 404
    get_resp = client.get(f"/workflows/{wf_id}", headers=headers)
    assert get_resp.status_code == 404

    # DB cascades
    db_wf = db_session.get(Workflow, wf_id)
    assert db_wf is None
    db_versions = db_session.query(WorkflowVersion).filter_by(workflow_id=wf_id).all()
    assert len(db_versions) == 0


def test_viewer_rbac_permissions(client):
    admin_headers = register_and_login(client, "Org Owner", "owner@firm.com")
    client.post("/organizations", json={"name": "Firm"}, headers=admin_headers)

    # Admin creates workflow
    created = client.post(
        "/workflows",
        json={"name": "Firm Flow", "definition": SAMPLE_DEFINITION},
        headers=admin_headers,
    ).json()
    wf_id = created["id"]

    # Invite viewer
    inv_resp = client.post(
        "/organizations/invitations",
        json={"email": "viewer@firm.com", "role": "Viewer"},
        headers=admin_headers,
    )
    token = inv_resp.json()["token"]

    viewer_headers = register_and_login(client, "Viewer User", "viewer@firm.com")
    client.post("/organizations/invitations/accept", json={"token": token}, headers=viewer_headers)

    # Viewer CAN list workflows
    v_list = client.get("/workflows", headers=viewer_headers)
    assert v_list.status_code == 200
    assert len(v_list.json()) == 1

    # Viewer CAN view workflow detail
    v_get = client.get(f"/workflows/{wf_id}", headers=viewer_headers)
    assert v_get.status_code == 200

    # Viewer CANNOT create
    v_create = client.post(
        "/workflows",
        json={"name": "Hacked Flow", "definition": SAMPLE_DEFINITION},
        headers=viewer_headers,
    )
    assert v_create.status_code == 403

    # Viewer CANNOT update
    v_update = client.put(
        f"/workflows/{wf_id}",
        json={"name": "Hacked Name"},
        headers=viewer_headers,
    )
    assert v_update.status_code == 403

    # Viewer CANNOT delete
    v_delete = client.delete(f"/workflows/{wf_id}", headers=viewer_headers)
    assert v_delete.status_code == 403


def test_organization_isolation(client):
    # Org 1
    org1_headers = register_and_login(client, "User 1", "u1@org1.com")
    client.post("/organizations", json={"name": "Org 1"}, headers=org1_headers)
    wf1 = client.post(
        "/workflows",
        json={"name": "Org 1 Secret Flow", "definition": SAMPLE_DEFINITION},
        headers=org1_headers,
    ).json()

    # Org 2
    org2_headers = register_and_login(client, "User 2", "u2@org2.com")
    client.post("/organizations", json={"name": "Org 2"}, headers=org2_headers)

    # User 2 cannot see Org 1 workflow in list
    u2_list = client.get("/workflows", headers=org2_headers).json()
    assert len(u2_list) == 0

    # User 2 cannot get Org 1 workflow
    u2_get = client.get(f"/workflows/{wf1['id']}", headers=org2_headers)
    assert u2_get.status_code == 404

    # User 2 cannot update Org 1 workflow
    u2_put = client.put(f"/workflows/{wf1['id']}", json={"name": "Hacked"}, headers=org2_headers)
    assert u2_put.status_code == 404

    # User 2 cannot delete Org 1 workflow
    u2_del = client.delete(f"/workflows/{wf1['id']}", headers=org2_headers)
    assert u2_del.status_code == 404


def test_multi_organization_membership_default_resolution(client, db_session):
    """
    Verifies existing multi-org resolution behavior:
    When a user belongs to multiple organizations and calls /workflows,
    _get_membership() resolves the user's primary/first organization (ordered by Membership.id).
    """
    from app.modules.workflows.service import create_workflow
    from app.modules.workflows.schemas import WorkflowCreateRequest

    # User 1 creates Org Alpha
    user1_headers = register_and_login(client, "Multi User", "multi@user.com")
    alpha_resp = client.post("/organizations", json={"name": "Org Alpha"}, headers=user1_headers)
    alpha_id = alpha_resp.json()["id"]

    # User 2 creates Org Beta
    user2_headers = register_and_login(client, "Beta Admin", "admin@beta.com")
    beta_resp = client.post("/organizations", json={"name": "Org Beta"}, headers=user2_headers)
    beta_id = beta_resp.json()["id"]

    # User 2 invites User 1 to Org Beta as Editor
    inv_resp = client.post(
        "/organizations/invitations",
        json={"email": "multi@user.com", "role": "Editor"},
        headers=user2_headers,
    )
    token = inv_resp.json()["token"]
    client.post("/organizations/invitations/accept", json={"token": token}, headers=user1_headers)

    # User 1 creates a workflow via API (no organization_id in request)
    created_resp = client.post(
        "/workflows",
        json={"name": "Alpha Flow", "definition": SAMPLE_DEFINITION},
        headers=user1_headers,
    )
    assert created_resp.status_code == 201
    created = created_resp.json()

    # Confirms it resolved to Org Alpha (first membership)
    assert created["organization_id"] == alpha_id

    # Beta Admin does not see it
    beta_list = client.get("/workflows", headers=user2_headers).json()
    assert len(beta_list) == 0

    # Service-level verification: internal callers can specify organization_id explicitly
    from app.database.models import User
    user1_obj = db_session.query(User).filter_by(email="multi@user.com").first()
    beta_flow = create_workflow(
        db=db_session,
        user_id=user1_obj.id,
        data=WorkflowCreateRequest(name="Beta Flow Direct", definition=SAMPLE_DEFINITION),
        organization_id=beta_id,
    )
    assert beta_flow.organization_id == beta_id

    # Beta Admin now sees Beta Flow
    beta_list_after = client.get("/workflows", headers=user2_headers).json()
    assert len(beta_list_after) == 1
    assert beta_list_after[0]["name"] == "Beta Flow Direct"

