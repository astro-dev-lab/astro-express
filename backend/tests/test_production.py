"""Unit contracts using fake storage; these do NOT prove PostgreSQL behavior."""
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app


def test_production_requires_ack_https_and_database():
    with pytest.raises(ValueError):
        Settings(mode="production")
    settings = Settings(mode="production", origin="https://localhost:8443", production_ack="I_ACCEPT_PRODUCTION_SECURITY_REQUIREMENTS", database_url="postgresql://localhost/astro")
    assert settings.mode == "production"

@pytest.mark.parametrize("url", ["sqlite:///tmp/a", "postgresql://remote.example/db", "", "postgresql://localhost/db?host=remote.example"])
def test_database_is_local_postgres_only(url):
    with pytest.raises(ValueError):
        Settings(mode="production", origin="https://localhost:8443", production_ack="I_ACCEPT_PRODUCTION_SECURITY_REQUIREMENTS", database_url=url)


def test_password_argon2():
    from app.auth import hash_password, verify_password
    hashed = hash_password("unit-test-password-123")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "unit-test-password-123")
    assert not verify_password(hashed, "wrong-password")

from app.config import ACK
from app.main import COOKIE
from app.auth import token_hash
from tests.fakes import FakeStore, PASSWORD

PRODUCTION_ORIGIN = "https://localhost:8443"
HEADERS = {"Origin": PRODUCTION_ORIGIN}


def settings():
    return Settings(mode="production", origin=PRODUCTION_ORIGIN, production_ack=ACK, database_url="postgresql://localhost/astro")

@pytest.fixture
def store():
    return FakeStore()

@pytest.fixture
def client(store):
    with TestClient(create_app(settings(), repository=store), base_url=PRODUCTION_ORIGIN) as client:
        yield client


def credential_login(client, username="admin", password=PASSWORD):
    return client.post("/api/auth/login", headers=HEADERS, json={"username":username,"password":password})


def test_production_config_no_demo_and_no_password_echo(client):
    assert client.get("/api/auth/config").json() == {"mode":"production", "credential_login":True}
    assert client.post("/api/auth/demo-login", headers=HEADERS).status_code == 404
    result = client.post("/api/auth/login", headers=HEADERS, json={"username":"admin","password":PASSWORD,"unexpected":"secret-probe"})
    assert result.status_code == 422
    assert PASSWORD not in result.text and "secret-probe" not in result.text


def test_admin_login_cookie_rotation_logout_replay(client, store):
    result = credential_login(client)
    assert result.status_code == 200
    assert result.json()["user"]["role"] == "admin"
    assert "Secure" in result.headers["set-cookie"] and "HttpOnly" in result.headers["set-cookie"]
    old_token = client.cookies.get(COOKIE)
    assert old_token not in store.sessions and token_hash(old_token) in store.sessions
    result = credential_login(client)
    assert token_hash(old_token) not in store.sessions
    csrf = result.json()["csrf_token"]
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout", headers=HEADERS).status_code == 403
    token = client.cookies.get(COOKIE)
    assert client.post("/api/auth/logout", headers={**HEADERS,"X-CSRF-Token":csrf}).status_code == 200
    client.cookies.set(COOKIE,token)
    assert client.get("/api/auth/me").status_code == 401


def test_viewer_can_read_and_logout_but_cannot_mutate(client):
    response = credential_login(client,"viewer")
    headers = {**HEADERS,"X-CSRF-Token":response.json()["csrf_token"]}
    assert client.get("/api/integrations").status_code == 200
    assert client.get("/api/activity").status_code == 200
    assert client.post("/api/integrations/stripe/simulate", headers=headers,json={"action":"checkout-success"}).status_code == 403
    assert client.post("/api/admin/users/00000000-0000-0000-0000-000000000001/revoke-sessions",headers=headers).status_code == 403
    assert client.post("/api/auth/logout",headers=headers).status_code == 200


def test_block_and_role_changes_apply_to_existing_session(client,store):
    result = credential_login(client)
    headers = {**HEADERS,"X-CSRF-Token":result.json()["csrf_token"]}
    store.users["admin"]["role"]="viewer"
    assert client.post("/api/integrations/stripe/simulate",headers=headers,json={"action":"checkout-success"}).status_code == 403
    store.users["admin"]["blocked"]=True
    assert client.get("/api/auth/me").status_code == 401
    assert credential_login(client).status_code == 401


def test_admin_can_revoke_sessions(client,store):
    response = credential_login(client)
    headers = {**HEADERS,"X-CSRF-Token":response.json()["csrf_token"]}
    user_id = store.users["admin"]["id"]
    assert client.post(f"/api/admin/users/{user_id}/revoke-sessions",headers=headers).status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_failed_login_throttle_and_redacted_logs(client,caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="astro.security"):
        for _ in range(5):
            assert credential_login(client,password="secret-wrong-password").status_code == 401
        assert credential_login(client,password="secret-wrong-password").status_code == 429
    logs = " ".join(record.message for record in caplog.records if record.name == "astro.security")
    assert "secret-wrong-password" not in logs and "admin" not in logs
    assert "login_throttled" in logs


def test_production_db_down_redacted_and_https_required(client,store,caplog):
    store.available=False
    assert client.get("/healthz").status_code == 200
    response = client.get("/readyz")
    assert response.status_code == 503
    assert "synthetic-secret" not in response.text
    assert "synthetic-secret" not in caplog.text
    assert client.get("http://localhost:8443/api/auth/me").status_code == 400


def test_startup_fails_closed(store):
    store.available=False
    with pytest.raises(RuntimeError, match="startup blocked"):
        with TestClient(create_app(settings(),repository=store),base_url=PRODUCTION_ORIGIN):
            pass


def test_activity_user_scope_and_simulation_label(client,store):
    response = credential_login(client)
    headers = {**HEADERS,"X-CSRF-Token":response.json()["csrf_token"]}
    event = client.post("/api/integrations/google/simulate",headers=headers,json={"action":"calendar-event-created"}).json()
    assert event["mode"] == "simulated" and event["connected"] is False
    assert client.get("/api/activity").json()["events"] == [event]
    credential_login(client,"viewer")
    assert client.get("/api/activity").json()["events"] == []


def test_env_requires_explicit_origin(monkeypatch):
    monkeypatch.setenv("APP_MODE","production")
    monkeypatch.delenv("APP_ORIGIN",raising=False)
    with pytest.raises(ValueError,match="explicit APP_ORIGIN"):
        Settings.from_env()

@pytest.mark.parametrize("key",["PGHOSTADDR","PGSERVICE","PGSERVICEFILE","PGOPTIONS"])
def test_libpq_environment_overrides_rejected(monkeypatch,key):
    monkeypatch.setenv(key,"remote.example")
    with pytest.raises(ValueError,match="overrides"):
        settings()

@pytest.mark.parametrize("origin",["https://*", "https://*.example.com", "https://bad_host", "http://localhost:8443"])
def test_production_origin_rejected(origin):
    with pytest.raises(ValueError):
        Settings(mode="production",origin=origin,production_ack=ACK,database_url="postgresql://localhost/astro")


def test_production_unit_session_expiry(client,store):
    credential_login(client)
    key=token_hash(client.cookies.get(COOKIE))
    user_id,_=store.sessions[key]
    store.sessions[key]=(user_id,0)
    assert client.get("/api/auth/me").status_code == 401


def test_structured_log_fields_only_and_no_dsn_repr():
    from app.observability import event
    with pytest.raises(ValueError): event("arbitrary-password-secret","production")
    with pytest.raises(ValueError): event("login_success","secret-dsn")
    configured=Settings(mode="production",origin=PRODUCTION_ORIGIN,production_ack=ACK,database_url="postgresql://user:synthetic-secret@localhost/astro")
    assert "synthetic-secret" not in repr(configured)


def test_sandbox_state_is_explicitly_unconfigured(client):
    credential_login(client)
    providers=client.get('/api/integrations').json()['integrations']
    assert len(providers)==6
    assert all(p['sandbox_status']=='not_configured' and p['connected'] is False for p in providers)
