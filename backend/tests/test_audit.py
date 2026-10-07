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


def test_audit_log_complete_lifecycle(client):
    """
    Test the 5 audit events specified for Module 1:
    1. ORGANIZATION_CREATED
    2. MEMBER_INVITED
    3. INVITATION_ACCEPTED
    4. MEMBER_ROLE_UPDATED
    5. GET /organizations/audit-logs returns all 4 events in order.
    """
    # 1. Admin registers and creates organization -> ORGANIZATION_CREATED
    admin_headers = register_and_login(client, "Admin User", "admin@acme.com")
    create_org_resp = client.post(
        "/organizations",
        json={"name": "Acme Corp"},
        headers=admin_headers,
    )
    assert create_org_resp.status_code == 201
    org_id = create_org_resp.json()["id"]

    # Verify ORGANIZATION_CREATED audit event
    audit_resp1 = client.get(f"/organizations/audit-logs?organization_id={org_id}", headers=admin_headers)
    assert audit_resp1.status_code == 200
    logs1 = audit_resp1.json()
    assert len(logs1) == 1
    assert logs1[0]["action"] == "ORGANIZATION_CREATED"
    assert logs1[0]["resource_type"] == "Organization"
    assert logs1[0]["resource_id"] == org_id
    assert logs1[0]["details"] == "Organization created"

    # 2. Invite Rahul -> MEMBER_INVITED
    invite_resp = client.post(
        f"/organizations/invitations?organization_id={org_id}",
        json={"email": "rahul@test.com", "role": "Editor"},
        headers=admin_headers,
    )
    assert invite_resp.status_code == 201
    invitation = invite_resp.json()
    invite_token = invitation["token"]

    # Verify MEMBER_INVITED audit event
    audit_resp2 = client.get(f"/organizations/audit-logs?organization_id={org_id}", headers=admin_headers)
    assert audit_resp2.status_code == 200
    logs2 = audit_resp2.json()
    assert len(logs2) == 2
    assert logs2[1]["action"] == "MEMBER_INVITED"
    assert logs2[1]["resource_type"] == "Invitation"
    assert logs2[1]["resource_id"] == invitation["id"]
    assert "rahul@test.com" in logs2[1]["details"]
    assert invite_token not in logs2[1]["details"]  # Never store tokens in audit details!

    # 3. Rahul registers and accepts invitation -> INVITATION_ACCEPTED
    rahul_headers = register_and_login(client, "Rahul Verma", "rahul@test.com")
    accept_resp = client.post(
        "/organizations/invitations/accept",
        json={"token": invite_token},
        headers=rahul_headers,
    )
    assert accept_resp.status_code == 200

    # Verify INVITATION_ACCEPTED audit event
    audit_resp3 = client.get(f"/organizations/audit-logs?organization_id={org_id}", headers=admin_headers)
    assert audit_resp3.status_code == 200
    logs3 = audit_resp3.json()
    assert len(logs3) == 3
    assert logs3[2]["action"] == "INVITATION_ACCEPTED"
    assert logs3[2]["resource_type"] == "Membership"
    assert "Editor" in logs3[2]["details"]

    # 4. Admin updates Rahul's role: Editor -> Viewer -> MEMBER_ROLE_UPDATED
    members_resp = client.get(f"/organizations/members?organization_id={org_id}", headers=admin_headers)
    members = members_resp.json()
    rahul_member = next(m for m in members if m["email"] == "rahul@test.com")

    update_role_resp = client.patch(
        f"/organizations/members/{rahul_member['id']}?organization_id={org_id}",
        json={"role": "Viewer"},
        headers=admin_headers,
    )
    assert update_role_resp.status_code == 200

    # 5. Call GET /organizations/audit-logs -> All 4 events present in sequence
    audit_resp4 = client.get(f"/organizations/audit-logs?organization_id={org_id}", headers=admin_headers)
    assert audit_resp4.status_code == 200
    all_logs = audit_resp4.json()
    assert len(all_logs) == 4

    expected_actions = [
        "ORGANIZATION_CREATED",
        "MEMBER_INVITED",
        "INVITATION_ACCEPTED",
        "MEMBER_ROLE_UPDATED",
    ]
    actual_actions = [log["action"] for log in all_logs]
    assert actual_actions == expected_actions

    # Check details of MEMBER_ROLE_UPDATED
    assert all_logs[3]["action"] == "MEMBER_ROLE_UPDATED"
    assert "Role changed from Editor to Viewer" in all_logs[3]["details"]

    # Member Rahul (now Viewer) can also view audit logs of the organization
    rahul_audit_resp = client.get(f"/organizations/audit-logs?organization_id={org_id}", headers=rahul_headers)
    assert rahul_audit_resp.status_code == 200
    assert len(rahul_audit_resp.json()) == 4

    # Non-member cannot access audit logs
    outsider_headers = register_and_login(client, "Outsider", "outsider@other.com")
    outsider_resp = client.get(f"/organizations/audit-logs?organization_id={org_id}", headers=outsider_headers)
    assert outsider_resp.status_code == 403
