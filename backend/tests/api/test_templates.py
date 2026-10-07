import pytest
from fastapi.testclient import TestClient

def test_list_templates(client: TestClient, db_session):
    # Ensure they are seeded
    from app.modules.templates.seed import seed_templates
    seed_templates(db_session)

    response = client.get("/templates/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3
    assert data[0]["name"] == "New Customer → CRM Lead"
    assert "definition" not in data[0]  # Should be summary only

def test_get_template(client: TestClient, db_session):
    # Ensure they are seeded
    from app.modules.templates.seed import seed_templates
    seed_templates(db_session)

    # Get the list first
    list_response = client.get("/templates/")
    first_template_id = list_response.json()[0]["id"]

    # Get detail
    response = client.get(f"/templates/{first_template_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Customer → CRM Lead"
    assert "definition" in data
    assert "setup_schema" in data

def test_get_unknown_template(client: TestClient):
    response = client.get("/templates/999999")
    assert response.status_code == 404
