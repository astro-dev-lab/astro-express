"""REAL PostgreSQL tests. Skipped without explicit disposable local DB authority.

No fake/SQLite replacement. Requires existing empty astro_test_* database,
TEST_DATABASE_URL and TEST_DATABASE_CONFIRM equal its exact database name.
These tests apply/revert migrations and delete test data in that database.
"""
import os
import secrets
from urllib.parse import urlsplit
import pytest
from app.migrate import migrate
from app.store import PostgresStore
from app.auth import hash_password, token_hash

DATABASE = os.getenv("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE, reason="No TEST_DATABASE_URL; real PostgreSQL, restart/migration and backup proof blocked")

@pytest.fixture
def database():
    name = urlsplit(DATABASE).path.lstrip("/")
    if not name.startswith("astro_test_") or os.getenv("TEST_DATABASE_CONFIRM") != name:
        pytest.fail("Exact disposable TEST_DATABASE_CONFIRM required")
    migrate(DATABASE, "up")
    store = PostgresStore(DATABASE)
    store.ready()
    yield store
    migrate(DATABASE,"down",name)


def test_real_migrations_idempotent_and_downgrade(database):
    migrate(DATABASE,"up")
    assert database.ready()
    name=urlsplit(DATABASE).path.lstrip("/")
    migrate(DATABASE,"down",name)
    migrate(DATABASE,"up")
    assert database.ready()


def test_real_users_sessions_restart_and_revocation(database):
    user_id=database.create_user("synthetic_admin","Synthetic Admin","admin",hash_password("synthetic-test-password-123"))
    token=secrets.token_urlsafe(32)
    database.create_session(user_id,token)
    restarted=PostgresStore(DATABASE)
    assert str(restarted.session_user(token)["id"])==user_id
    with restarted.connection() as conn:
        row=conn.execute("SELECT token_hash FROM app_sessions WHERE user_id=%s",(user_id,)).fetchone()
    assert row["token_hash"]==token_hash(token) and row["token_hash"]!=token
    restarted.revoke_user_sessions(user_id)
    assert database.session_user(token) is None


def test_real_activity_user_isolation_and_bounded_history(database):
    uid=database.create_user("synthetic_one","Synthetic One","admin",hash_password("synthetic-test-password-123"))
    other=database.create_user("synthetic_two","Synthetic Two","viewer",hash_password("synthetic-test-password-123"))
    for i in range(102): database.record_activity(uid,{"synthetic":i})
    restarted=PostgresStore(DATABASE)
    assert len(restarted.activity(uid))==100
    assert restarted.activity(uid)[0]=={"synthetic":101}
    assert restarted.activity(other)==[]


def test_real_block_and_expiry(database):
    uid=database.create_user("synthetic_block","Synthetic Block","viewer",hash_password("synthetic-test-password-123"))
    token=secrets.token_urlsafe(32)
    database.create_session(uid,token)
    database.change_user("synthetic_block",blocked=True)
    assert database.session_user(token) is None
    database.change_user("synthetic_block",blocked=False)
    database.create_session(uid,token)
    with database.connection() as conn:
        conn.execute("UPDATE app_sessions SET expires_at=now()-interval '1 second' WHERE token_hash=%s",(token_hash(token),))
    assert database.session_user(token) is None
