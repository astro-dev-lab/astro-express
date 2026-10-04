"""Actual isolated LOCAL PostgreSQL proof, never substitute a fake."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
import psycopg
import pytest
from app.auth import hash_password
from app.migrate import migrate
from app.store import PostgresStore
from app.corporate import Actor, CorporateStore, GuardError, migrate_corporate

URL = os.getenv("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="Actual PostgreSQL unavailable")

@pytest.fixture
def corporate():
    name = urlsplit(URL).path.lstrip("/")
    assert name.startswith("astro_test_") and os.getenv("TEST_DATABASE_CONFIRM") == name
    migrate(URL)
    base = PostgresStore(URL)
    uid = base.create_user("synthetic_owner", "Synthetic Owner", "admin", hash_password("synthetic-test-password-123"))
    other = base.create_user("synthetic_other", "Synthetic Other", "admin", hash_password("synthetic-test-password-123"))
    migrate_corporate(base)
    store = CorporateStore(base)
    store.provision_owner("synthetic_owner")
    yield store, Actor(uid, "human"), Actor(other, "human")
    migrate_corporate(base, "down", name)
    migrate(URL, "down", name)


def project_and_work(store, actor, key=None):
    project = store.create_project(actor, "Synthetic Project")
    work = store.intake(actor, project["id"], key or str(uuid.uuid4()), {"title": "Synthetic task", "objective": "Improve local quality", "acceptance": "Local tests pass"})
    return project, work


def approve(store, actor, work):
    return store.approve(actor, work["id"], work["digest"], "APPROVE_ZERO_COST_CONTRACT")


def test_migration_idempotent_and_p1_schema_unchanged(corporate):
    store, owner, _ = corporate
    migrate_corporate(store.base)
    assert store.base.ready() and store.snapshot(owner)["costs"]["limit_cents"] == 0
    with store.base.connection() as conn:
        assert conn.execute("SELECT max(version) AS v FROM schema_migrations").fetchone()["v"] == 1


def test_intake_idempotency_concurrency_and_conflict(corporate):
    store, owner, _ = corporate
    project = store.create_project(owner, "Synthetic")
    payload = {"title":"Synthetic", "objective":"Local code", "acceptance":"Tests pass"}
    def submit(_): return store.intake(owner, project["id"], "same-key", payload)
    with ThreadPoolExecutor(max_workers=4) as pool: results = list(pool.map(submit, range(4)))
    assert len({str(x["id"]) for x in results}) == 1
    assert len(store.snapshot(owner)["work"]) == 1
    with pytest.raises(GuardError): store.intake(owner, project["id"], "same-key", {**payload, "title":"Changed"})


def test_no_dispatch_without_distinct_owner_approval(corporate):
    store, owner, _ = corporate
    _, work = project_and_work(store, owner)
    with pytest.raises(GuardError): store.dispatch(owner, work["id"])
    assert store.snapshot(owner)["approvals"] == []
    assert store.snapshot(owner)["jobs"] == []
    approve(store, owner, work)
    job = store.dispatch(owner, work["id"])
    assert job["status"] == "BLOCKED_UPSTREAM_AUTHORIZATION" and job["mode"] == "contract"


def test_approval_rejects_service_other_owner_digest_and_confirmation(corporate):
    store, owner, other = corporate
    _, work = project_and_work(store, owner)
    for actor, digest, confirm in [(Actor(owner.id,"service"),work["digest"],"APPROVE_ZERO_COST_CONTRACT"),(other,work["digest"],"APPROVE_ZERO_COST_CONTRACT"),(owner,"0"*64,"APPROVE_ZERO_COST_CONTRACT"),(owner,work["digest"],"yes")]:
        with pytest.raises(GuardError): store.approve(actor,work["id"],digest,confirm)
    assert store.snapshot(owner)["approvals"] == []


def test_expired_approval_and_blocked_owner_fail_closed(corporate):
    store, owner, _ = corporate
    _, work = project_and_work(store,owner)
    approve(store,owner,work)
    from datetime import datetime, timedelta, timezone
    with pytest.raises(GuardError): store.dispatch(owner,work["id"],now=datetime.now(timezone.utc)+timedelta(days=2))
    store.base.change_user("synthetic_owner",blocked=True)
    with pytest.raises(GuardError): store.snapshot(owner)


def test_dispatch_and_actual_cost_are_idempotent_and_durable(corporate):
    store, owner, _ = corporate
    _, work = project_and_work(store,owner)
    approve(store,owner,work)
    with ThreadPoolExecutor(max_workers=4) as pool: jobs=list(pool.map(lambda _:store.dispatch(owner,work["id"]),range(4)))
    assert len({str(x["id"]) for x in jobs}) == 1
    job=jobs[0]
    store.record_actual(owner,job["id"],0,"proof-1")
    store.record_actual(owner,job["id"],0,"proof-1")
    restarted=CorporateStore(PostgresStore(URL))
    snapshot=restarted.snapshot(owner)
    assert len(snapshot["jobs"])==1 and len(snapshot["costs"]["actuals"])==1
    assert snapshot["costs"]["reserved_cents"]==snapshot["costs"]["actual_cents"]==0


@pytest.mark.parametrize("cents",[-1,1,20000])
def test_no_new_paid_reservation_or_actual(corporate,cents):
    store,owner,_=corporate
    _,work=project_and_work(store,owner)
    approve(store,owner,work)
    with pytest.raises(GuardError): store.dispatch(owner,work["id"],reserve_cents=cents)
    job=store.dispatch(owner,work["id"])
    with pytest.raises(GuardError): store.record_actual(owner,job["id"],cents,"invalid")
    assert store.snapshot(owner)["costs"]["actuals"]==[]


def test_immutable_audit_and_approval_and_budget_constraints(corporate):
    store,owner,_=corporate
    _,work=project_and_work(store,owner)
    approve(store,owner,work)
    for sql in ["UPDATE corporate_audit SET event='tampered'", "DELETE FROM corporate_audit", "TRUNCATE corporate_audit", "UPDATE corporate_approvals SET digest='tampered'", "UPDATE corporate_budget SET limit_cents=1"]:
        with pytest.raises(psycopg.Error):
            with store.base.connection() as conn: conn.execute(sql)
    events=store.snapshot(owner)["audit"]
    assert {x["event"] for x in events} >= {"owner_provisioned","project_created","work_submitted","work_approved"}
    assert not any("password" in str(x) for x in events)


def test_corporate_downgrade_preserves_p1(corporate):
    store,owner,_=corporate
    with pytest.raises(GuardError): migrate_corporate(store.base,"down","wrong")
    name=urlsplit(URL).path.lstrip("/")
    migrate_corporate(store.base,"down",name)
    assert store.base.ready() and store.base.user_by_username("synthetic_owner")
    migrate_corporate(store.base)


def test_actual_api_owner_csrf_origin_viewer_logout_and_no_implicit_approval(corporate):
    from fastapi.testclient import TestClient
    from app.config import Settings, ACK
    from app.main import create_app, COOKIE
    store,owner,_=corporate
    origin='https://localhost:8443'
    settings=Settings(mode='production',origin=origin,production_ack=ACK,database_url=URL)
    with TestClient(create_app(settings),base_url=origin) as client:
        assert client.get('/api/corporate/snapshot').status_code==401
        login=client.post('/api/auth/login',headers={'Origin':origin},json={'username':'synthetic_owner','password':'synthetic-test-password-123'})
        assert login.status_code==200
        headers={'Origin':origin,'X-CSRF-Token':login.json()['csrf_token']}
        assert client.post('/api/corporate/projects',headers={'Origin':origin},json={'name':'Synthetic'}).status_code==403
        assert client.post('/api/corporate/projects',headers={**headers,'Origin':'https://attacker.example'},json={'name':'Synthetic'}).status_code==403
        assert client.post('/api/corporate/projects',headers=headers,json={'name':'Synthetic','repository_url':'https://attacker.example'}).status_code==422
        project=client.post('/api/corporate/projects',headers=headers,json={'name':'Synthetic'}).json()
        work=client.post('/api/corporate/work',headers=headers,json={'project_id':project['id'],'request_key':'api-proof','title':'Local task','objective':'Local quality','acceptance':'Tests pass'}).json()
        snapshot=client.get('/api/corporate/snapshot').json()
        assert snapshot['approvals']==snapshot['jobs']==[]
        denied=client.post('/api/corporate/work/'+work['id']+'/dispatch-contract',headers=headers,json={})
        assert denied.status_code==409 and denied.headers['x-content-type-options']=='nosniff'
        assert client.post('/api/corporate/work/'+work['id']+'/approve',headers=headers,json={'digest':work['digest'],'confirmation':'APPROVE_ZERO_COST_CONTRACT'}).status_code==200
        assert client.post('/api/corporate/work/'+work['id']+'/dispatch-contract',headers=headers,json={'reserve_cents':1}).status_code==409
        assert client.post('/api/corporate/work/'+work['id']+'/dispatch-contract',headers=headers,json={}).json()['status']=='BLOCKED_UPSTREAM_AUTHORIZATION'
        old_cookie=client.cookies.get(COOKIE)
        assert client.post('/api/auth/logout',headers=headers,json={}).status_code==200
        client.cookies.set(COOKIE,old_cookie)
        assert client.get('/api/corporate/snapshot').status_code==401
    with TestClient(create_app(settings),base_url=origin) as other:
        assert other.post('/api/auth/login',headers={'Origin':origin},json={'username':'synthetic_other','password':'synthetic-test-password-123'}).status_code==200
        assert other.get('/api/corporate/snapshot').status_code==409
    store.base.change_user('synthetic_other',role='viewer')
    with TestClient(create_app(settings),base_url=origin) as viewer:
        login=viewer.post('/api/auth/login',headers={'Origin':origin},json={'username':'synthetic_other','password':'synthetic-test-password-123'})
        assert login.status_code==200
        assert viewer.post('/api/corporate/projects',headers={'Origin':origin,'X-CSRF-Token':login.json()['csrf_token']},json={'name':'Denied'}).status_code==403


def test_unknown_schema_and_actual_conflicting_reference_fail_closed(corporate):
    store,owner,_=corporate
    _,work=project_and_work(store,owner)
    approve(store,owner,work)
    job=store.dispatch(owner,work['id'])
    store.record_actual(owner,job['id'],0,'same-proof')
    with pytest.raises(GuardError): store.record_actual(owner,job['id'],0,'different-proof')
    with store.base.connection() as conn: conn.execute('INSERT INTO corporate_schema_migrations VALUES(0)')
    with pytest.raises(GuardError): migrate_corporate(store.base)
    with pytest.raises(GuardError): store.snapshot(owner)
    with store.base.connection() as conn: conn.execute('DELETE FROM corporate_schema_migrations WHERE version=0')
