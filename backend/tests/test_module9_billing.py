"""
Module 9: Flat, Predictable Billing & Subscription Tests

Verifies:
1. Public plan catalog endpoint (/billing/plans) with flat workflow limits and zero task metering.
2. Default organization subscription initialization (Free tier: 2 active workflows).
3. Real-time workflow usage metrics (active, paused, draft, total, percentage).
4. Workflow publish limit enforcement (Free tier allows 2 published workflows; 3rd is blocked with HTTP 402).
5. Pausing an active workflow frees up quota, permitting publishing of another workflow.
6. Self-serve plan upgrade (Free -> Starter with 5 workflows quota, Pro with 15, Enterprise with unlimited).
7. Role-based access control (Admin allowed to mutate; Editor and Viewer blocked with HTTP 403).
8. Multi-tenant quota isolation between organizations.
9. Audit trail logging for subscription updates and cancellations.
"""

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


def sample_workflow_payload(name: str = "Automation Workflow"):
    return {
        "name": name,
        "description": "Test workflow for billing validation",
        "definition": {
            "trigger": {
                "connector": "google_sheets",
                "event": "new_row",
                "config": {"spreadsheet_id": "sheet_123"},
            },
            "steps": [
                {
                    "id": "step-1",
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


def setup_org_with_connectors(client, email: str, org_name: str):
    headers = register_and_login(client, "Billing Admin", email)
    org_resp = client.post("/organizations", json={"name": org_name}, headers=headers).json()
    org_id = org_resp["id"]

    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": f"{org_name} Sheet",
            "config": {"spreadsheet_id": "sheet_123"},
            "credentials": {"client_id": "svc@google.com", "client_secret": "sec_123"},
        },
        headers=headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": f"{org_name} CRM",
            "config": {},
            "credentials": {"api_key": "crm_key_123"},
        },
        headers=headers,
    )

    return headers, org_id


# ============================================================================
# 1. Plan Catalog Tests
# ============================================================================

def test_get_plan_catalog(client):
    resp = client.get("/billing/plans")
    assert resp.status_code == 200
    data = resp.json()

    assert data["pricing_model"] == "flat_workflow_count"
    assert "Zero task-based metering" in data["guarantee"]
    plans = data["plans"]
    assert len(plans) == 4

    tiers = {p["tier"]: p for p in plans}
    assert "free" in tiers
    assert "starter" in tiers
    assert "pro" in tiers
    assert "enterprise" in tiers

    assert tiers["free"]["max_active_workflows"] == 2
    assert tiers["free"]["execution_limit"] == "unlimited"
    assert tiers["free"]["price_usd_monthly"] == 0

    assert tiers["starter"]["max_active_workflows"] == 5
    assert tiers["starter"]["execution_limit"] == "unlimited"
    assert tiers["starter"]["price_usd_monthly"] == 19

    assert tiers["pro"]["max_active_workflows"] == 15
    assert tiers["pro"]["execution_limit"] == "unlimited"
    assert tiers["pro"]["price_usd_monthly"] == 49

    assert tiers["enterprise"]["max_active_workflows"] is None
    assert tiers["enterprise"]["execution_limit"] == "unlimited"
    assert tiers["enterprise"]["price_usd_monthly"] == 149


# ============================================================================
# 2. Subscription Initialization & Usage Metrics Tests
# ============================================================================

def test_default_subscription_and_usage_metrics(client):
    headers, org_id = setup_org_with_connectors(client, "admin1@test.com", "Acme Logistics")

    resp = client.get("/billing/subscription", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Subscription defaults to Free
    sub = data["subscription"]
    assert sub["plan_tier"] == "free"
    assert sub["status"] == "active"
    assert sub["billing_cycle"] == "monthly"
    assert sub["cancel_at_period_end"] is False
    assert data["can_manage_billing"] is True

    # Usage begins at 0
    usage = data["usage"]
    assert usage["active_workflows"] == 0
    assert usage["max_active_workflows"] == 2
    assert usage["usage_percentage"] == 0.0
    assert usage["is_limit_reached"] is False
    assert usage["remaining_slots"] == 2


# ============================================================================
# 3. Workflow Limit Enforcement at Publish
# ============================================================================

def test_workflow_publish_limit_enforcement(client):
    headers, org_id = setup_org_with_connectors(client, "admin2@test.com", "Beta Retail")

    # Create 3 workflows
    wf1_id = client.post("/workflows", json=sample_workflow_payload("Flow 1"), headers=headers).json()["id"]
    wf2_id = client.post("/workflows", json=sample_workflow_payload("Flow 2"), headers=headers).json()["id"]
    wf3_id = client.post("/workflows", json=sample_workflow_payload("Flow 3"), headers=headers).json()["id"]

    # Publish 1st workflow -> 1/2 used
    pub1 = client.post(f"/workflows/{wf1_id}/publish", headers=headers)
    assert pub1.status_code == 200
    assert pub1.json()["status"] == "published"

    usage1 = client.get("/billing/subscription", headers=headers).json()["usage"]
    assert usage1["active_workflows"] == 1
    assert usage1["remaining_slots"] == 1
    assert usage1["usage_percentage"] == 50.0

    # Publish 2nd workflow -> 2/2 used (Limit reached)
    pub2 = client.post(f"/workflows/{wf2_id}/publish", headers=headers)
    assert pub2.status_code == 200
    assert pub2.json()["status"] == "published"

    usage2 = client.get("/billing/subscription", headers=headers).json()["usage"]
    assert usage2["active_workflows"] == 2
    assert usage2["remaining_slots"] == 0
    assert usage2["is_limit_reached"] is True
    assert usage2["usage_percentage"] == 100.0

    # Attempt to publish 3rd workflow -> Blocked with HTTP 402 Payment Required!
    pub3 = client.post(f"/workflows/{wf3_id}/publish", headers=headers)
    assert pub3.status_code == 402
    err_detail = pub3.json()["detail"]
    assert "Plan limit reached" in err_detail
    assert "maximum of 2 active workflows for the 'Free' plan" in err_detail
    assert "Upgrade your subscription" in err_detail

    # Pausing 1st workflow frees up a slot
    pause1 = client.post(f"/workflows/{wf1_id}/pause", headers=headers)
    assert pause1.status_code == 200
    assert pause1.json()["status"] == "paused"

    usage_after_pause = client.get("/billing/subscription", headers=headers).json()["usage"]
    assert usage_after_pause["active_workflows"] == 1
    assert usage_after_pause["remaining_slots"] == 1
    assert usage_after_pause["is_limit_reached"] is False

    # Now publishing 3rd workflow succeeds!
    pub3_again = client.post(f"/workflows/{wf3_id}/publish", headers=headers)
    assert pub3_again.status_code == 200
    assert pub3_again.json()["status"] == "published"

    # Now attempting to resume/publish workflow 1 is blocked because 2 and 3 are active
    pub1_retry = client.post(f"/workflows/{wf1_id}/publish", headers=headers)
    assert pub1_retry.status_code == 402


# ============================================================================
# 4. Self-Serve Plan Upgrade Flow
# ============================================================================

def test_self_serve_upgrade_and_quota_expansion(client):
    headers, org_id = setup_org_with_connectors(client, "admin3@test.com", "Gamma Supply")

    # Create 3 workflows and publish 2
    wf1_id = client.post("/workflows", json=sample_workflow_payload("Flow 1"), headers=headers).json()["id"]
    wf2_id = client.post("/workflows", json=sample_workflow_payload("Flow 2"), headers=headers).json()["id"]
    wf3_id = client.post("/workflows", json=sample_workflow_payload("Flow 3"), headers=headers).json()["id"]

    client.post(f"/workflows/{wf1_id}/publish", headers=headers)
    client.post(f"/workflows/{wf2_id}/publish", headers=headers)

    # 3rd is blocked on Free plan
    assert client.post(f"/workflows/{wf3_id}/publish", headers=headers).status_code == 402

    # Admin upgrades to Starter ($19/mo, 5 workflows)
    upgrade_resp = client.post(
        "/billing/subscription",
        json={"plan_tier": "starter", "billing_cycle": "annual"},
        headers=headers,
    )
    assert upgrade_resp.status_code == 200
    upgraded_data = upgrade_resp.json()
    assert upgraded_data["subscription"]["plan_tier"] == "starter"
    assert upgraded_data["subscription"]["billing_cycle"] == "annual"
    assert upgraded_data["usage"]["max_active_workflows"] == 5
    assert upgraded_data["usage"]["remaining_slots"] == 3
    assert upgraded_data["usage"]["is_limit_reached"] is False

    # Now publishing 3rd workflow succeeds immediately!
    pub3 = client.post(f"/workflows/{wf3_id}/publish", headers=headers)
    assert pub3.status_code == 200
    assert pub3.json()["status"] == "published"

    # Upgrade to Enterprise (unlimited)
    ent_resp = client.post(
        "/billing/subscription",
        json={"plan_tier": "enterprise", "billing_cycle": "monthly"},
        headers=headers,
    )
    assert ent_resp.status_code == 200
    ent_data = ent_resp.json()
    assert ent_data["subscription"]["plan_tier"] == "enterprise"
    assert ent_data["usage"]["max_active_workflows"] is None
    assert ent_data["usage"]["remaining_slots"] is None
    assert ent_data["usage"]["is_limit_reached"] is False


# ============================================================================
# 5. Role-Based Access Control (RBAC)
# ============================================================================

def test_billing_rbac_permissions(client):
    admin_headers, org_id = setup_org_with_connectors(client, "admin4@test.com", "Delta Security")

    # Invite an Editor and a Viewer
    client.post(
        "/organizations/invitations",
        json={"email": "editor@delta.com", "role": "Editor"},
        headers=admin_headers,
    )
    client.post(
        "/organizations/invitations",
        json={"email": "viewer@delta.com", "role": "Viewer"},
        headers=admin_headers,
    )

    editor_headers = register_and_login(client, "Delta Editor", "editor@delta.com")
    viewer_headers = register_and_login(client, "Delta Viewer", "viewer@delta.com")

    # Accept invites
    editor_invites = client.get("/organizations/invitations/pending", headers=editor_headers).json()
    client.post("/organizations/invitations/accept", json={"token": editor_invites[0]["token"]}, headers=editor_headers)

    viewer_invites = client.get("/organizations/invitations/pending", headers=viewer_headers).json()
    client.post("/organizations/invitations/accept", json={"token": viewer_invites[0]["token"]}, headers=viewer_headers)

    # 1. Editor and Viewer can VIEW billing subscription & usage
    editor_view = client.get(f"/billing/subscription?organization_id={org_id}", headers=editor_headers)
    assert editor_view.status_code == 200
    assert editor_view.json()["can_manage_billing"] is False

    viewer_view = client.get(f"/billing/subscription?organization_id={org_id}", headers=viewer_headers)
    assert viewer_view.status_code == 200
    assert viewer_view.json()["can_manage_billing"] is False

    # 2. Editor and Viewer CANNOT mutate subscription
    editor_upgrade = client.post(
        f"/billing/subscription?organization_id={org_id}",
        json={"plan_tier": "pro"},
        headers=editor_headers,
    )
    assert editor_upgrade.status_code == 403
    assert "Only organization Admins" in editor_upgrade.json()["detail"]

    viewer_cancel = client.post(
        f"/billing/cancel?organization_id={org_id}",
        headers=viewer_headers,
    )
    assert viewer_cancel.status_code == 403
    assert "Only organization Admins" in viewer_cancel.json()["detail"]


# ============================================================================
# 6. Multi-Tenancy Quota Isolation
# ============================================================================

def test_multitenant_quota_isolation(client):
    headers_a, org_a_id = setup_org_with_connectors(client, "orgA_admin@test.com", "Tenant Alpha")
    headers_b, org_b_id = setup_org_with_connectors(client, "orgB_admin@test.com", "Tenant Bravo")

    # Max out Tenant Alpha (2 workflows)
    wf_a1 = client.post("/workflows", json=sample_workflow_payload("Alpha 1"), headers=headers_a).json()["id"]
    wf_a2 = client.post("/workflows", json=sample_workflow_payload("Alpha 2"), headers=headers_a).json()["id"]
    wf_a3 = client.post("/workflows", json=sample_workflow_payload("Alpha 3"), headers=headers_a).json()["id"]

    client.post(f"/workflows/{wf_a1}/publish", headers=headers_a)
    client.post(f"/workflows/{wf_a2}/publish", headers=headers_a)
    assert client.post(f"/workflows/{wf_a3}/publish", headers=headers_a).status_code == 402

    # Tenant Bravo should still have full 2/2 quota available and publish without issue
    wf_b1 = client.post("/workflows", json=sample_workflow_payload("Bravo 1"), headers=headers_b).json()["id"]
    pub_b1 = client.post(f"/workflows/{wf_b1}/publish", headers=headers_b)
    assert pub_b1.status_code == 200
    assert pub_b1.json()["status"] == "published"

    b_usage = client.get("/billing/subscription", headers=headers_b).json()["usage"]
    assert b_usage["active_workflows"] == 1
    assert b_usage["remaining_slots"] == 1


# ============================================================================
# 7. Cancellation and Audit Trail
# ============================================================================

def test_subscription_cancellation_and_audit_trail(client):
    headers, org_id = setup_org_with_connectors(client, "admin5@test.com", "Epsilon Manufacturing")

    # Upgrade first
    client.post(
        "/billing/subscription",
        json={"plan_tier": "pro", "billing_cycle": "monthly"},
        headers=headers,
    )

    # Cancel subscription
    cancel_resp = client.post("/billing/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["cancel_at_period_end"] is True

    # Subscription state reflects cancellation scheduled
    sub_data = client.get("/billing/subscription", headers=headers).json()["subscription"]
    assert sub_data["cancel_at_period_end"] is True

    # Check Audit Logs
    audit_resp = client.get(f"/organizations/audit-logs?organization_id={org_id}", headers=headers)
    assert audit_resp.status_code == 200
    actions = [log["action"] for log in audit_resp.json()]
    assert "subscription.updated" in actions
    assert "subscription.canceled" in actions
