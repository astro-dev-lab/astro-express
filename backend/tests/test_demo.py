import socket
import time
import pytest
from fastapi.testclient import TestClient
from app.main import COOKIE, FIXTURES, MAX_SESSIONS, Session, create_app
from app.config import Settings

ORIGIN = {"Origin": "http://127.0.0.1:8000"}

@pytest.fixture
def client():
    with TestClient(create_app(), base_url="http://127.0.0.1:8000") as client:
        yield client

def login(client):
    response = client.post("/api/auth/demo-login", headers=ORIGIN)
    assert response.status_code == 200
    return {**ORIGIN, "X-CSRF-Token": response.json()["csrf_token"]}

def test_health_and_unauthorized(client):
    assert client.get("/healthz").json() == {"status":"ok", "mode":"simulation"}
    for route in ["/api/auth/me", "/api/integrations", "/api/activity"]:
        assert client.get(route).status_code == 401

def test_login_cookie_logout_and_replay(client):
    headers = login(client)
    token = client.cookies.get(COOKIE)
    cookie = client.get("/api/auth/me").headers
    assert client.get("/api/auth/me").json()["user"]["id"] == "demo-admin"
    assert client.post("/api/auth/logout", headers=ORIGIN).status_code == 403
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set(COOKIE, token)
    assert client.get("/api/auth/me").status_code == 401

def test_cookie_flags_rotation(client):
    response = client.post("/api/auth/demo-login", headers=ORIGIN)
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    old = client.cookies.get(COOKIE)
    login(client)
    assert old not in client.app.state.sessions

@pytest.mark.parametrize("origin", [None, "https://evil.test", "http://127.0.0.1:8000.evil.test", "null"])
def test_origin_rejected(client, origin):
    assert client.post("/api/auth/demo-login", headers={} if origin is None else {"Origin":origin}).status_code == 403

def test_host_and_fetch_site(client):
    assert client.get("/healthz", headers={"Host":"evil.test"}).status_code == 400
    assert client.post("/api/auth/demo-login", headers={**ORIGIN,"Sec-Fetch-Site":"cross-site"}).status_code == 403

@pytest.mark.parametrize("mode", ["production", "live", "", "mock"])
def test_config_fails_closed(mode):
    with pytest.raises(ValueError): Settings(mode=mode)

@pytest.mark.parametrize("origin", ["https://example.com", "http://localhost:8000/path", "http://u:p@localhost:8000", "http://localhost:8000?x", "file://localhost"])
def test_bad_origin_config(origin):
    with pytest.raises(ValueError): Settings(origin=origin)

@pytest.mark.parametrize("provider", list(FIXTURES))
@pytest.mark.parametrize("index", [1,2])
def test_all_fixture_flows_without_sockets(client, monkeypatch, provider, index):
    headers = login(client)
    def denied(*args, **kwargs):
        raise AssertionError("Outbound socket forbidden")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    action = FIXTURES[provider][index]
    result = client.post(f"/api/integrations/{provider}/simulate", json={"action":action}, headers=headers)
    assert result.status_code == 200
    event = result.json()
    assert event["mode"] == "simulated" and event["connected"] is False
    assert event["status"] == ("success" if index == 1 else "failed")
    assert event["reference"].startswith("demo-")
    assert client.get("/api/activity").json()["events"] == [event]

def test_validation_csrf_and_unknown_provider(client):
    headers = login(client)
    assert client.post("/api/integrations/stripe/simulate", json={"action":"checkout-success"}, headers=ORIGIN).status_code == 403
    assert client.post("/api/integrations/missing/simulate", json={"action":"a"}, headers=headers).status_code == 404
    for body in [{"action":"live-payment"}, {"action":"checkout-success", "email":"a"}, {"action":1}]:
        assert client.post("/api/integrations/stripe/simulate", json=body, headers=headers).status_code == 422

def test_listing_isolation_unique_references_and_history_bound(client):
    headers = login(client)
    integrations = client.get("/api/integrations").json()["integrations"]
    assert len(integrations) == 6 and all(len(p["actions"]) == 2 for p in integrations)
    refs = set()
    for _ in range(105):
        event = client.post("/api/integrations/stripe/simulate", json={"action":"checkout-success"}, headers=headers).json()
        refs.add(event["reference"])
    assert len(refs) == 105
    assert len(client.get("/api/activity").json()["events"]) == 100
    with TestClient(client.app, base_url="http://127.0.0.1:8000") as second:
        login(second)
        assert second.get("/api/activity").json()["events"] == []

def test_session_expiry_and_limit(client):
    login(client)
    client.app.state.sessions[client.cookies.get(COOKIE)].expires = 0
    assert client.get("/api/auth/me").status_code == 401
    for i in range(MAX_SESSIONS):
        client.app.state.sessions[str(i)] = Session("csrf", time.monotonic()+3600)
    assert client.post("/api/auth/demo-login", headers=ORIGIN).status_code == 429

def test_https_cookie_security():
    with TestClient(create_app(Settings(origin="https://localhost:8000")), base_url="https://localhost:8000") as client:
        response = client.post("/api/auth/demo-login", headers={"Origin":"https://localhost:8000"})
        assert "Secure" in response.headers["set-cookie"]

def test_body_limit_with_and_without_content_length(client):
    assert client.post("/api/auth/demo-login", content=b"x"*4097, headers=ORIGIN).status_code == 413
    assert client.post("/api/auth/demo-login", content=iter([b"x"*3000,b"x"*2000]), headers=ORIGIN).status_code == 413

@pytest.mark.parametrize("origin", ["http://localhost:nope", "http://localhost:999999"])
def test_bad_port_config(origin):
    with pytest.raises(ValueError): Settings(origin=origin)
