from datetime import datetime, timezone
from unittest.mock import patch
import pytest

from app.database.models import Notification, Workflow, WorkflowExecution
from app.modules.connectors.adapters.crm import CRMAdapter
from app.modules.executions.service import execute_workflow
from app.modules.notifications.service import check_and_notify_repeated_failure


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


def setup_monitoring_fixture(client, email: str = "m7_user@test.com", org_name: str = "M7 Monitoring Org") -> tuple[dict, int, int]:
    headers = register_and_login(client, "M7 Admin", email)
    org_id = client.post("/organizations", json={"name": org_name}, headers=headers).json()["id"]

    # Connectors
    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "M7 Sheet",
            "config": {"spreadsheet_id": "sheet_m7"},
            "credentials": {"client_id": "svc@g.com", "client_secret": "sec_oauth_123"},
        },
        headers=headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "M7 CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "sec_crm_123"},
        },
        headers=headers,
    )

    # Workflow 1 (Published)
    wf_payload = {
        "name": "Customer Lead Sync",
        "definition": {
            "trigger": {
                "connector": "google_sheets",
                "event": "new_row",
                "config": {"spreadsheet_id": "sheet_m7"},
            },
            "steps": [
                {
                    "id": "create_lead",
                    "type": "action",
                    "connector": "crm",
                    "action": "create_lead",
                    "config": {},
                    "mapping": {"name": "trigger.values.Name", "email": "trigger.values.Email"},
                }
            ],
        },
    }
    wf1_id = client.post("/workflows", json=wf_payload, headers=headers).json()["id"]
    client.post(f"/workflows/{wf1_id}/publish", headers=headers)

    return headers, org_id, wf1_id


# ============================================================================
# Tests: Monitoring Dashboard & Usage APIs
# ============================================================================

def test_dashboard_overview_metrics(client, db_session):
    headers, org_id, wf_id = setup_monitoring_fixture(client, "dash_metric@test.com", "Dash Org")

    # Initially: 1 published workflow, 0 executions
    resp = client.get("/monitoring/dashboard?period_days=30", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["period_days"] == 30
    assert data["workflow_summary"]["total"] == 1
    assert data["workflow_summary"]["published"] == 1
    assert data["workflow_summary"]["paused"] == 0
    assert data["workflow_summary"]["draft"] == 0
    assert data["execution_metrics"]["total_runs"] == 0
    assert data["execution_metrics"]["success_rate"] == 100.0

    # 1. Run successful execution
    with patch.object(CRMAdapter, "execute_action", return_value={"lead_id": "lead_101"}):
        execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data={"values": {"Name": "Ramesh", "Email": "ramesh@acme.com"}},
            organization_id=org_id,
        )

    # 2. Run failed execution
    with patch.object(CRMAdapter, "execute_action", side_effect=Exception("External CRM service timed out")):
        execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data={"values": {"Name": "Suresh", "Email": "suresh@acme.com"}},
            organization_id=org_id,
        )

    # Query dashboard again
    resp2 = client.get("/monitoring/dashboard?period_days=30", headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()

    assert data2["execution_metrics"]["total_runs"] == 2
    assert data2["execution_metrics"]["successful_runs"] == 1
    assert data2["execution_metrics"]["failed_runs"] == 1
    assert data2["execution_metrics"]["success_rate"] == 50.0
    assert len(data2["timeline"]) >= 1

    # Check workflow enrichment
    assert len(data2["workflows"]) == 1
    wf_item = data2["workflows"][0]
    assert wf_item["id"] == wf_id
    assert wf_item["total_runs"] == 2
    assert wf_item["success_runs"] == 1
    assert wf_item["failed_runs"] == 1
    assert wf_item["tasks_this_month"] == 2
    assert wf_item["last_run_status"] == "failed"


def test_monthly_usage_stats(client, db_session):
    headers, org_id, wf_id = setup_monitoring_fixture(client, "usage_test@test.com", "Usage Org")

    # Run 2 successful executions
    with patch.object(CRMAdapter, "execute_action", return_value={"lead_id": "ok"}):
        for i in range(2):
            execute_workflow(
                db=db_session,
                workflow_id=wf_id,
                trigger_data={"values": {"Name": f"User {i}", "Email": f"user{i}@test.com"}},
                organization_id=org_id,
            )

    now = datetime.now(timezone.utc)
    resp = client.get(f"/monitoring/usage?year={now.year}&month={now.month}", headers=headers)
    assert resp.status_code == 200
    usage = resp.json()

    assert usage["total_tasks_this_month"] == 2
    assert usage["total_successful_tasks"] == 2
    assert usage["total_failed_tasks"] == 0
    assert usage["active_workflows_count"] == 1
    assert len(usage["workflow_usage"]) == 1
    assert usage["workflow_usage"][0]["tasks_this_month"] == 2
    assert usage["workflow_usage"][0]["percentage_of_total"] == 100.0


def test_monitoring_workflows_endpoint(client, db_session):
    headers, org_id, wf_id = setup_monitoring_fixture(client, "wf_mon@test.com", "WF Mon Org")

    resp = client.get("/monitoring/workflows", headers=headers)
    assert resp.status_code == 200
    wfs = resp.json()
    assert len(wfs) == 1
    assert wfs[0]["name"] == "Customer Lead Sync"


# ============================================================================
# Tests: Automated Failure Detection & In-App Notifications
# ============================================================================

def test_repeated_failure_notification_generation_and_deduplication(client, db_session):
    headers, org_id, wf_id = setup_monitoring_fixture(client, "notif_rep@test.com", "Notif Rep Org")

    # 1. First failure -> consecutive_failures = 1 (Threshold 2 not reached, no notification)
    with patch.object(CRMAdapter, "execute_action", side_effect=Exception("Network connection failed")):
        execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data={"values": {"Name": "Fail 1", "Email": "fail1@test.com"}},
            organization_id=org_id,
        )

    notifs_resp = client.get("/notifications", headers=headers)
    assert notifs_resp.status_code == 200
    assert notifs_resp.json()["total"] == 0

    # 2. Second failure -> consecutive_failures = 2 (Threshold reached! Notification created!)
    with patch.object(CRMAdapter, "execute_action", side_effect=Exception("Network connection failed")):
        execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data={"values": {"Name": "Fail 2", "Email": "fail2@test.com"}},
            organization_id=org_id,
        )

    notifs_resp2 = client.get("/notifications", headers=headers)
    assert notifs_resp2.status_code == 200
    data2 = notifs_resp2.json()
    assert data2["total"] == 1
    assert data2["unread_count"] == 1
    notif = data2["items"][0]
    assert "Failed Repeatedly (2x)" in notif["title"]
    assert notif["workflow_id"] == wf_id
    assert notif["is_read"] is False
    assert notif["severity"] == "warning"

    # 3. Third failure -> consecutive_failures = 3 (Updates existing unread notification, no spam!)
    with patch.object(CRMAdapter, "execute_action", side_effect=Exception("Network connection failed")):
        execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data={"values": {"Name": "Fail 3", "Email": "fail3@test.com"}},
            organization_id=org_id,
        )

    notifs_resp3 = client.get("/notifications", headers=headers)
    assert notifs_resp3.status_code == 200
    data3 = notifs_resp3.json()
    assert data3["total"] == 1  # Still 1 notification! No duplicate created
    assert "Failed Repeatedly (3x)" in data3["items"][0]["title"]
    assert data3["items"][0]["severity"] == "critical"  # Escalates to critical on 3+ failures


def test_notification_read_and_delete_lifecycle(client, db_session):
    headers, org_id, wf_id = setup_monitoring_fixture(client, "notif_crud@test.com", "Notif CRUD Org")

    # Cause 2 failures to generate notification
    with patch.object(CRMAdapter, "execute_action", side_effect=Exception("CRM API rate limit exceeded")):
        execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data={"values": {"Name": "A", "Email": "a@a.com"}},
            organization_id=org_id,
        )
        execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data={"values": {"Name": "B", "Email": "b@b.com"}},
            organization_id=org_id,
        )

    unread_resp = client.get("/notifications/unread-count", headers=headers)
    assert unread_resp.status_code == 200
    assert unread_resp.json()["unread_count"] == 1

    list_resp = client.get("/notifications", headers=headers)
    notif_id = list_resp.json()["items"][0]["id"]

    # Mark as read
    patch_resp = client.patch(f"/notifications/{notif_id}/read", headers=headers)
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_read"] is True

    unread_resp2 = client.get("/notifications/unread-count", headers=headers)
    assert unread_resp2.json()["unread_count"] == 0

    # Mark all read endpoint
    mark_all = client.post("/notifications/mark-all-read", headers=headers)
    assert mark_all.status_code == 200

    # Delete notification
    del_resp = client.delete(f"/notifications/{notif_id}", headers=headers)
    assert del_resp.status_code == 204

    # Now empty
    final_list = client.get("/notifications", headers=headers)
    assert final_list.json()["total"] == 0


def test_monitoring_tenant_isolation(client, db_session):
    # Org A
    headers_a, org_a_id, wf_a_id = setup_monitoring_fixture(client, "org_a@test.com", "Org A")
    # Org B
    headers_b, org_b_id, wf_b_id = setup_monitoring_fixture(client, "org_b@test.com", "Org B")

    # Run executions in Org A only
    with patch.object(CRMAdapter, "execute_action", return_value={"lead_id": "lead_a"}):
        execute_workflow(
            db=db_session,
            workflow_id=wf_a_id,
            trigger_data={"values": {"Name": "A", "Email": "a@org.com"}},
            organization_id=org_a_id,
        )

    # Check Org A sees 1 run
    dash_a = client.get("/monitoring/dashboard", headers=headers_a).json()
    assert dash_a["execution_metrics"]["total_runs"] == 1

    # Check Org B sees 0 runs
    dash_b = client.get("/monitoring/dashboard", headers=headers_b).json()
    assert dash_b["execution_metrics"]["total_runs"] == 0

    # Org B attempts to query Org A's data explicitly -> forbidden or scoped to user
    resp_cross = client.get(f"/monitoring/dashboard?organization_id={org_a_id}", headers=headers_b)
    # User B is not a member of Org A -> returns 404
    assert resp_cross.status_code == 404


def test_monitoring_unauthenticated_forbidden(client):
    assert client.get("/monitoring/dashboard").status_code == 401
    assert client.get("/monitoring/usage").status_code == 401
    assert client.get("/notifications").status_code == 401
    assert client.get("/notifications/unread-count").status_code == 401
