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


def test_create_and_get_organization(client):
    headers = register_and_login(client, "Alice Admin", "alice@test.com")

    # Create organization
    create_resp = client.post(
        "/organizations",
        json={"name": "Acme Corp"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    org = create_resp.json()
    assert org["name"] == "Acme Corp"
    assert "id" in org

    # Get current organization
    me_resp = client.get("/organizations/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["name"] == "Acme Corp"
    assert me_resp.json()["role"] == "Admin"

    # List organizations
    list_resp = client.get("/organizations", headers=headers)
    assert list_resp.status_code == 200
    orgs = list_resp.json()
    assert len(orgs) == 1
    assert orgs[0]["name"] == "Acme Corp"
    assert orgs[0]["role"] == "Admin"


def test_get_organization_members(client):
    headers = register_and_login(client, "Admin User", "admin@org.com")
    client.post("/organizations", json={"name": "Tech Corp"}, headers=headers)

    members_resp = client.get("/organizations/members", headers=headers)
    assert members_resp.status_code == 200
    members = members_resp.json()
    assert len(members) == 1
    assert members[0]["name"] == "Admin User"
    assert members[0]["email"] == "admin@org.com"
    assert members[0]["role"] == "Admin"


def test_invite_member_flow(client):
    admin_headers = register_and_login(client, "Org Admin", "admin@company.com")
    client.post("/organizations", json={"name": "Company X"}, headers=admin_headers)

    # 1. Invite a new email
    invite_resp = client.post(
        "/organizations/invitations",
        json={"email": "employee@company.com", "role": "Editor"},
        headers=admin_headers,
    )
    assert invite_resp.status_code == 201
    invite_data = invite_resp.json()
    token = invite_data["token"]
    assert invite_data["email"] == "employee@company.com"
    assert invite_data["role"] == "Editor"
    assert invite_data["status"] == "pending"

    # 2. Duplicate invite check
    dup_invite = client.post(
        "/organizations/invitations",
        json={"email": "EMPLOYEE@company.com", "role": "Viewer"},
        headers=admin_headers,
    )
    assert dup_invite.status_code == 400
    assert "already pending" in dup_invite.json()["detail"].lower()

    # 3. Employee registers and sees pending invite
    emp_headers = register_and_login(client, "Employee One", "employee@company.com")
    pending_resp = client.get("/organizations/invitations/pending", headers=emp_headers)
    assert pending_resp.status_code == 200
    pending_list = pending_resp.json()
    assert len(pending_list) == 1
    assert pending_list[0]["email"] == "employee@company.com"

    # 4. Another user cannot accept someone else's invite
    other_headers = register_and_login(client, "Intruder", "intruder@company.com")
    intruder_accept = client.post(
        "/organizations/invitations/accept",
        json={"token": token},
        headers=other_headers,
    )
    assert intruder_accept.status_code == 403

    # 5. Employee accepts invitation
    accept_resp = client.post(
        "/organizations/invitations/accept",
        json={"token": token},
        headers=emp_headers,
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["role"] == "Editor"

    # 6. Verify employee is now in members list
    members_resp = client.get("/organizations/members", headers=admin_headers)
    assert len(members_resp.json()) == 2

    # 7. Inviting an existing member should fail
    re_invite = client.post(
        "/organizations/invitations",
        json={"email": "employee@company.com", "role": "Viewer"},
        headers=admin_headers,
    )
    assert re_invite.status_code == 400
    assert "already a member" in re_invite.json()["detail"].lower()


def test_non_admin_cannot_invite(client):
    admin_headers = register_and_login(client, "Boss", "boss@corp.com")
    client.post("/organizations", json={"name": "Corp"}, headers=admin_headers)

    invite_resp = client.post(
        "/organizations/invitations",
        json={"email": "worker@corp.com", "role": "Viewer"},
        headers=admin_headers,
    )
    token = invite_resp.json()["token"]

    worker_headers = register_and_login(client, "Worker", "worker@corp.com")
    client.post("/organizations/invitations/accept", json={"token": token}, headers=worker_headers)

    # Worker (Viewer) tries to invite
    unauth_invite = client.post(
        "/organizations/invitations",
        json={"email": "newbie@corp.com", "role": "Viewer"},
        headers=worker_headers,
    )
    assert unauth_invite.status_code == 403


def test_update_member_role(client):
    admin_headers = register_and_login(client, "Admin", "admin@team.com")
    client.post("/organizations", json={"name": "Team Org"}, headers=admin_headers)

    invite_resp = client.post(
        "/organizations/invitations",
        json={"email": "developer@team.com", "role": "Viewer"},
        headers=admin_headers,
    )
    token = invite_resp.json()["token"]

    dev_headers = register_and_login(client, "Developer", "developer@team.com")
    client.post("/organizations/invitations/accept", json={"token": token}, headers=dev_headers)

    # Get members list to find developer's id
    members = client.get("/organizations/members", headers=admin_headers).json()
    dev_member = next(m for m in members if m["email"] == "developer@team.com")
    dev_id = dev_member["id"]

    # Admin updates developer role from Viewer to Editor
    patch_resp = client.patch(
        f"/organizations/members/{dev_id}",
        json={"role": "Editor"},
        headers=admin_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["role"] == "Editor"

    # Developer (Editor) cannot change admin's role
    admin_member = next(m for m in members if m["email"] == "admin@team.com")
    admin_id = admin_member["id"]
    unauth_patch = client.patch(
        f"/organizations/members/{admin_id}",
        json={"role": "Viewer"},
        headers=dev_headers,
    )
    assert unauth_patch.status_code == 403

    # Admin cannot demote the sole Admin of the org
    demote_sole_admin = client.patch(
        f"/organizations/members/{admin_id}",
        json={"role": "Viewer"},
        headers=admin_headers,
    )
    assert demote_sole_admin.status_code == 400
    assert "sole admin" in demote_sole_admin.json()["detail"].lower()


def test_multi_organization_membership(client):
    # User 1 creates Org 1
    user1_headers = register_and_login(client, "User One", "user1@multiorg.com")
    client.post("/organizations", json={"name": "Org Alpha"}, headers=user1_headers)

    # User 2 creates Org 2
    user2_headers = register_and_login(client, "User Two", "user2@multiorg.com")
    client.post("/organizations", json={"name": "Org Beta"}, headers=user2_headers)

    # User 2 invites User 1 to Org Beta as Editor
    invite_resp = client.post(
        "/organizations/invitations",
        json={"email": "user1@multiorg.com", "role": "Editor"},
        headers=user2_headers,
    )
    token = invite_resp.json()["token"]

    # User 1 accepts
    client.post(
        "/organizations/invitations/accept",
        json={"token": token},
        headers=user1_headers,
    )

    # User 1 should now be in 2 organizations
    my_orgs = client.get("/organizations", headers=user1_headers).json()
    assert len(my_orgs) == 2
    org_names = {o["name"]: o["role"] for o in my_orgs}
    assert org_names["Org Alpha"] == "Admin"
    assert org_names["Org Beta"] == "Editor"
