"""Migration transaction contracts with driver spies; not real PostgreSQL proof."""
import pytest
from app import migrate
from app.store import PostgresStore

class Cursor:
    def __init__(self, rows=()): self.rows=rows
    def fetchall(self): return self.rows

class Connection:
    def __init__(self, versions=()): self.versions=versions; self.calls=[]; self.committed=False; self.rolled_back=False
    def __enter__(self): return self
    def __exit__(self, typ, exc, tb):
        self.committed=typ is None
        self.rolled_back=typ is not None
    def execute(self, sql, params=None):
        self.calls.append((sql,params))
        return Cursor([(v,) for v in self.versions]) if sql.startswith("SELECT version") else Cursor()


def test_migration_lock_order_and_idempotence(monkeypatch):
    conn=Connection([1])
    kwargs=[]
    def connect(url,**options): kwargs.append(options); return conn
    monkeypatch.setattr(migrate.psycopg,"connect",connect)
    migrate.migrate("postgresql://localhost/astro_test_unit")
    assert "pg_advisory_xact_lock" in conn.calls[0][0]
    assert not any("INSERT INTO schema_migrations" in sql for sql,_ in conn.calls)
    assert kwargs[0]["hostaddr"] == "127.0.0.1" and conn.committed


def test_unknown_version_rolls_back(monkeypatch):
    conn=Connection([2])
    monkeypatch.setattr(migrate.psycopg,"connect",lambda *a,**k:conn)
    with pytest.raises(ValueError): migrate.migrate("postgresql://localhost/astro_test_unit")
    assert conn.rolled_back and not any("DROP" in sql for sql,_ in conn.calls)

@pytest.mark.parametrize("url,confirm",[("postgresql://localhost/astro","astro"),("postgresql://localhost/astro_test_unit",None),("postgresql://localhost/astro_test_unit","wrong")])
def test_downgrade_requires_disposable_exact_confirmation(url,confirm):
    with pytest.raises(ValueError): migrate.migrate(url,"down",confirm)


def test_connection_uses_explicit_ipv6_address(monkeypatch):
    kwargs=[]
    monkeypatch.setattr(migrate.psycopg,"connect",lambda *a,**k:kwargs.append(k))
    PostgresStore("postgresql://[::1]/astro").connection()
    assert kwargs[0]["hostaddr"] == "::1"


def test_new_migration_reads_packaged_sql_and_records_version(monkeypatch):
    conn=Connection([])
    monkeypatch.setattr(migrate.psycopg,"connect",lambda *a,**k:conn)
    migrate.migrate("postgresql://localhost/astro_test_unit")
    assert conn.committed
    assert any("CREATE TABLE app_users" in sql and "CREATE TABLE app_sessions" in sql for sql,_ in conn.calls)
    assert ("INSERT INTO schema_migrations(version) VALUES (%s)",(1,)) in conn.calls


def test_confirmed_disposable_downgrade_reads_sql(monkeypatch):
    conn=Connection([1])
    monkeypatch.setattr(migrate.psycopg,"connect",lambda *a,**k:conn)
    migrate.migrate("postgresql://localhost/astro_test_unit","down","astro_test_unit")
    assert conn.committed
    assert any("DROP TABLE app_users" in sql for sql,_ in conn.calls)
    assert ("DELETE FROM schema_migrations WHERE version=%s",(1,)) in conn.calls
