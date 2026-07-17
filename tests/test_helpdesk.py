from fastapi.testclient import TestClient


def client():
    from app.main import create_app
    return TestClient(create_app(database_url="sqlite://"))


def login(c, email, password):
    response = c.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_health_and_login():
    c = client()
    assert c.get("/api/health").json() == {"status": "ok"}
    token = c.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin123"}).json()
    assert token["token_type"] == "bearer"


def test_technician_can_close_ticket_through_explicit_close_endpoint():
    c = client()
    requester = login(c, "requester@example.com", "requester123")
    technician = login(c, "technician@example.com", "technician123")
    ticket = c.post("/api/tickets", headers=requester, json={"title": "Projector is broken", "description": "Room A101", "category": "Hardware", "priority": "High"})

    response = c.post(f"/api/tickets/{ticket.json()['id']}/close", headers=technician)

    assert response.status_code == 200
    assert response.json()["status"] == "Closed"


def test_ticket_history_endpoint_exposes_assignment_records_to_requester():
    c = client()
    requester = login(c, "requester@example.com", "requester123")
    technician = login(c, "technician@example.com", "technician123")
    ticket = c.post("/api/tickets", headers=requester, json={"title": "Projector is broken", "description": "Room A101", "category": "Hardware", "priority": "High"})
    ticket_id = ticket.json()["id"]
    assert c.patch(f"/api/tickets/{ticket_id}/assign", headers=technician, json={"assignee_id": 3}).status_code == 200

    response = c.get(f"/api/tickets/{ticket_id}/history", headers=requester)

    assert response.status_code == 200
    assert any(event["event_type"] == "assigned" and event["detail"] == "Assigned to Technician" for event in response.json()["items"])


def test_role_restriction_and_ticket_lifecycle():
    c = client()
    requester = login(c, "requester@example.com", "requester123")
    technician = login(c, "technician@example.com", "technician123")
    assert c.get("/api/users", headers=requester).status_code == 403
    ticket = c.post("/api/tickets", headers=requester, json={"title":"Projector is broken","description":"Room A101","category":"Hardware","priority":"High"})
    assert ticket.status_code == 201
    ticket_id = ticket.json()["id"]
    assert c.get("/api/tickets", headers=requester).json()["items"][0]["id"] == ticket_id
    assert c.get(f"/api/tickets/{ticket_id}", headers=requester).status_code == 200
    assert c.patch(f"/api/tickets/{ticket_id}/assign", headers=technician, json={"assignee_id": 3}).status_code == 200
    assert c.post(f"/api/tickets/{ticket_id}/comments", headers=requester, json={"body":"Please help soon"}).status_code == 201
    assert c.patch(f"/api/tickets/{ticket_id}/status", headers=technician, json={"status":"In Progress"}).json()["status"] == "In Progress"
    detail = c.get(f"/api/tickets/{ticket_id}", headers=requester).json()
    assert len(detail["comments"]) == 1 and any(event["event_type"] == "status_changed" for event in detail["history"])


def test_required_frontend_pages_render_their_page_specific_content():
    c = client()

    for path, heading in [("/login", "HelpDesk EDU login"), ("/", "HelpDesk EDU Dashboard"), ("/tickets", "HelpDesk EDU Tickets")]:
        response = c.get(path)
        assert response.status_code == 200
        assert f"<h1>{heading}</h1>" in response.text


def test_frontend_ticket_form_creates_ticket_and_redirects_to_detail():
    c = client()

    response = c.post(
        "/tickets/new",
        data={
            "title": "Cannot access virtual campus",
            "description": "The student cannot access the virtual campus with current credentials.",
            "category": "Access",
            "priority": "High",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = response.headers.get("location")
    assert location is not None
    assert location.startswith("/tickets/")
    detail = c.get(location)
    assert detail.status_code == 200
    assert "Cannot access virtual campus" in detail.text


def test_frontend_login_sets_cookie_and_dashboard_shows_current_user():
    c = client()

    response = c.post(
        "/login",
        data={"email": "admin@example.com", "password": "admin123"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers.get("location") == "/"
    assert "helpdesk_token=" in response.headers.get("set-cookie", "")
    dashboard = c.get("/")
    assert dashboard.status_code == 200
    assert "Signed in as Admin" in dashboard.text
    assert "administrator" in dashboard.text


def test_dashboard_catalogs_and_web_pages():
    c = client()
    admin = login(c, "admin@example.com", "admin123")
    assert c.get("/api/catalogs", headers=admin).status_code == 200
    assert "status" in c.get("/api/dashboard", headers=admin).json()
    for path in ["/login", "/", "/tickets", "/tickets/new", "/knowledge-base"]:
        response = c.get(path, follow_redirects=False)
        assert response.status_code in (200, 303)
        if response.status_code == 200:
            assert "HelpDesk EDU" in response.text
