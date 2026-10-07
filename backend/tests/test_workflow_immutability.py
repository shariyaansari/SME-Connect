import pytest


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


def setup_connections_and_workflow(client, headers: dict) -> int:
    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Immutability Sheet",
            "config": {"spreadsheet_id": "sheet_immutable"},
            "credentials": {"client_id": "svc@google.com", "client_secret": "sec_imm"},
        },
        headers=headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Immutability CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "pat_imm"},
        },
        headers=headers,
    )

    payload = {
        "name": "Immutable Lead Sync",
        "description": "Version 1 pipeline",
        "definition": {
            "trigger": {
                "connector": "google_sheets",
                "event": "new_row",
                "config": {"spreadsheet_id": "sheet_immutable"},
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
    wf_resp = client.post("/workflows", json=payload, headers=headers)
    return wf_resp.json()["id"]


def test_published_version_cannot_be_modified(client, db_session):
    headers = register_and_login(client, "Lead Admin", "admin@immutable.com")
    client.post("/organizations", json={"name": "Immutability Org"}, headers=headers)
    wf_id = setup_connections_and_workflow(client, headers)

    # Publish V1
    pub_resp = client.post(f"/workflows/{wf_id}/publish", headers=headers)
    assert pub_resp.status_code == 200
    assert pub_resp.json()["status"] == "published"
    assert pub_resp.json()["version_number"] == 1

    # Attempt 1: API Level - explicitly target published version 1 for update
    attempt_api = client.put(
        f"/workflows/{wf_id}?version=1",
        json={
            "definition": {
                "trigger": {
                    "connector": "google_sheets",
                    "event": "new_row",
                    "config": {"spreadsheet_id": "sheet_mutated"},
                },
                "steps": [
                    {
                        "id": "create-lead",
                        "type": "action",
                        "connector": "crm",
                        "action": "create_lead",
                    }
                ],
            }
        },
        headers=headers,
    )
    assert attempt_api.status_code == 400
    assert "immutable" in attempt_api.json()["detail"].lower()

    # Attempt 2: Database / ORM Level - directly mutating definition raises ValueError
    from app.database.models import WorkflowVersion
    v1_model = db_session.query(WorkflowVersion).filter_by(workflow_id=wf_id, version_number=1).first()
    assert v1_model.published_at is not None

    with pytest.raises(ValueError) as exc_def:
        v1_model.definition = {"hacked": "definition"}
        db_session.commit()
    assert "immutable" in str(exc_def.value).lower()
    assert "definition" in str(exc_def.value).lower()
    db_session.rollback()

    # Attempt 3: Database / ORM Level - directly mutating published_at raises ValueError
    v1_model = db_session.query(WorkflowVersion).filter_by(workflow_id=wf_id, version_number=1).first()
    with pytest.raises(ValueError) as exc_pub:
        v1_model.published_at = None
        db_session.commit()
    assert "immutable" in str(exc_pub.value).lower()
    assert "published_at" in str(exc_pub.value).lower()
    db_session.rollback()

    # Attempt 4: Database / ORM Level - directly mutating version_number raises ValueError
    v1_model = db_session.query(WorkflowVersion).filter_by(workflow_id=wf_id, version_number=1).first()
    with pytest.raises(ValueError) as exc_ver:
        v1_model.version_number = 99
        db_session.commit()
    assert "immutable" in str(exc_ver.value).lower()
    assert "version_number" in str(exc_ver.value).lower()
    db_session.rollback()


def test_editing_published_workflow_creates_new_draft_version(client):
    headers = register_and_login(client, "Editor User", "editor@immutable.com")
    client.post("/organizations", json={"name": "Edit Org"}, headers=headers)
    wf_id = setup_connections_and_workflow(client, headers)

    # Publish V1
    client.post(f"/workflows/{wf_id}/publish", headers=headers)

    # Edit workflow without targeting a specific version
    updated_def = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
            "config": {"spreadsheet_id": "sheet_v2"},
        },
        "steps": [
            {
                "id": "create-lead-v2",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "config": {},
                "mapping": {
                    "name": "trigger.values.FullName",
                    "email": "trigger.values.WorkEmail",
                },
            }
        ],
    }
    edit_resp = client.put(
        f"/workflows/{wf_id}",
        json={"name": "Updated Pipeline Name", "definition": updated_def},
        headers=headers,
    )
    assert edit_resp.status_code == 200
    data = edit_resp.json()

    # Workflow is now Draft V2
    assert data["status"] == "draft"
    assert data["version_number"] == 2
    assert data["name"] == "Updated Pipeline Name"
    assert data["definition"]["steps"][0]["id"] == "create-lead-v2"

    # Versions list contains V2 (draft) and V1 (published historical)
    assert len(data["versions"]) == 2
    v2_info = next(v for v in data["versions"] if v["version_number"] == 2)
    assert v2_info["published_at"] is None
    assert v2_info["is_active"] is False

    v1_info = next(v for v in data["versions"] if v["version_number"] == 1)
    assert v1_info["published_at"] is not None
    assert v1_info["is_active"] is False


def test_historical_published_v1_remains_unchanged_after_v2_created_and_edited(client):
    headers = register_and_login(client, "Audit Lead", "audit@immutable.com")
    client.post("/organizations", json={"name": "Audit Org"}, headers=headers)
    wf_id = setup_connections_and_workflow(client, headers)

    # Publish V1
    v1_published = client.post(f"/workflows/{wf_id}/publish", headers=headers).json()
    v1_def_original = v1_published["definition"]
    v1_pub_time = v1_published["versions"][0]["published_at"]

    # Edit to spawn V2 Draft
    client.put(
        f"/workflows/{wf_id}",
        json={
            "definition": {
                "trigger": {
                    "connector": "google_sheets",
                    "event": "new_row",
                    "config": {"spreadsheet_id": "sheet_v2_edit1"},
                },
                "steps": [
                    {
                        "id": "step-v2",
                        "type": "action",
                        "connector": "crm",
                        "action": "create_lead",
                    }
                ],
            }
        },
        headers=headers,
    )

    # Further edit V2 Draft
    client.put(
        f"/workflows/{wf_id}",
        json={
            "definition": {
                "trigger": {
                    "connector": "google_sheets",
                    "event": "new_row",
                    "config": {"spreadsheet_id": "sheet_v2_edit2"},
                },
                "steps": [
                    {
                        "id": "step-v2-final",
                        "type": "action",
                        "connector": "crm",
                        "action": "create_lead",
                    }
                ],
            }
        },
        headers=headers,
    )

    # Fetch V1 explicitly via GET /workflows/{id}?version=1
    v1_fetch = client.get(f"/workflows/{wf_id}?version=1", headers=headers).json()
    assert v1_fetch["version_number"] == 1
    assert v1_fetch["definition"] == v1_def_original
    v1_summary = next(v for v in v1_fetch["versions"] if v["version_number"] == 1)
    assert v1_summary["published_at"] == v1_pub_time


def test_publishing_v2_does_not_alter_v1_definition_or_publication_timestamp(client):
    headers = register_and_login(client, "Release Manager", "rel@immutable.com")
    client.post("/organizations", json={"name": "Release Org"}, headers=headers)
    wf_id = setup_connections_and_workflow(client, headers)

    # Publish V1
    v1_initial = client.post(f"/workflows/{wf_id}/publish", headers=headers).json()
    v1_def_initial = v1_initial["definition"]
    v1_timestamp = v1_initial["versions"][0]["published_at"]

    # Edit definition (V2 Draft)
    v2_def = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
            "config": {"spreadsheet_id": "sheet_release_v2"},
        },
        "steps": [
            {
                "id": "create-lead-release-2",
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
    }
    client.put(f"/workflows/{wf_id}", json={"definition": v2_def}, headers=headers)

    # Publish V2
    pub2_resp = client.post(f"/workflows/{wf_id}/publish", headers=headers)
    assert pub2_resp.status_code == 200
    pub2_data = pub2_resp.json()
    assert pub2_data["status"] == "published"
    assert pub2_data["version_number"] == 2

    # Verify single active version invariant
    active_versions = [v for v in pub2_data["versions"] if v["is_active"]]
    assert len(active_versions) == 1
    assert active_versions[0]["version_number"] == 2

    # Historical V1 checks
    v1_check = client.get(f"/workflows/{wf_id}?version=1", headers=headers).json()
    assert v1_check["version_number"] == 1
    assert v1_check["definition"] == v1_def_initial
    v1_summary = next(v for v in v1_check["versions"] if v["version_number"] == 1)
    assert v1_summary["published_at"] == v1_timestamp
    assert v1_summary["is_active"] is False


def test_historical_versions_remain_readable(client):
    headers = register_and_login(client, "Inspector User", "inspect@immutable.com")
    client.post("/organizations", json={"name": "Inspect Org"}, headers=headers)
    wf_id = setup_connections_and_workflow(client, headers)

    # Publish V1
    client.post(f"/workflows/{wf_id}/publish", headers=headers)

    # Create & Publish V2
    v2_def = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
            "config": {"spreadsheet_id": "sheet_v2_readable"},
        },
        "steps": [
            {
                "id": "step-2",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "mapping": {"name": "trigger.values.Name"},
            }
        ],
    }
    client.put(f"/workflows/{wf_id}", json={"definition": v2_def}, headers=headers)
    client.post(f"/workflows/{wf_id}/publish", headers=headers)

    # 1. Read default -> returns latest published version (V2)
    default_read = client.get(f"/workflows/{wf_id}", headers=headers).json()
    assert default_read["version_number"] == 2
    assert default_read["definition"]["steps"][0]["id"] == "step-2"

    # 2. Read specific version 1 -> returns V1
    v1_read = client.get(f"/workflows/{wf_id}?version=1", headers=headers).json()
    assert v1_read["version_number"] == 1
    assert v1_read["definition"]["steps"][0]["id"] == "create-lead"

    # 3. Read specific version 2 -> returns V2
    v2_read = client.get(f"/workflows/{wf_id}?version=2", headers=headers).json()
    assert v2_read["version_number"] == 2
    assert v2_read["definition"]["steps"][0]["id"] == "step-2"

    # 4. Read non-existent version 99 -> returns 404
    non_existent = client.get(f"/workflows/{wf_id}?version=99", headers=headers)
    assert non_existent.status_code == 404
    assert "version 99 not found" in non_existent.json()["detail"].lower()
