"""Small parameterized PostgreSQL repository; connections never use remote hosts.

No ORM, no migration-on-startup, no raw driver errors in application responses/logs.
"""
from datetime import datetime, timedelta, timezone
import json
import uuid
from urllib.parse import urlsplit
import psycopg
from psycopg.rows import dict_row
from .auth import token_hash
from .config import validate_database_url

SCHEMA_VERSION = 1


class StoreUnavailable(Exception):
    """Redacted database availability error."""


class PostgresStore:
    def __init__(self, database_url):
        self.database_url = validate_database_url(database_url)

    def connection(self):
        validate_database_url(self.database_url)
        return psycopg.connect(self.database_url, hostaddr="::1" if urlsplit(self.database_url).hostname == "::1" else "127.0.0.1", connect_timeout=3, options="-c statement_timeout=3000", row_factory=dict_row)

    def ready(self):
        with self.connection() as conn:
            row = conn.execute("SELECT max(version) AS version FROM schema_migrations").fetchone()
            if not row or row["version"] != SCHEMA_VERSION:
                raise StoreUnavailable("Database schema is not ready")
            conn.execute("SELECT u.id,s.token_hash,e.payload,l.bucket FROM app_users u,app_sessions s,activity_events e,auth_limits l LIMIT 0")
        return True

    def user_by_username(self, username):
        with self.connection() as conn:
            return conn.execute("SELECT id, username, display_name, role, password_hash, blocked FROM app_users WHERE username=%s", (username,)).fetchone()

    def allow_login_attempt(self, username):
        # Persistent account + global throttles. Never store IP or plaintext password.
        now = datetime.now(timezone.utc)
        key = token_hash("login:" + username)
        with self.connection() as conn:
            for bucket, window, limit in [("global", 60, 100), (key, 900, 5)]:
                row = conn.execute("""INSERT INTO auth_limits (bucket, started_at, attempts) VALUES (%s,%s,1)
                    ON CONFLICT (bucket) DO UPDATE SET
                    attempts=CASE WHEN auth_limits.started_at < %s THEN 1 ELSE auth_limits.attempts+1 END,
                    started_at=CASE WHEN auth_limits.started_at < %s THEN %s ELSE auth_limits.started_at END
                    RETURNING attempts""", (bucket, now, now-timedelta(seconds=window), now-timedelta(seconds=window), now)).fetchone()
                if row["attempts"] > limit:
                    return False
            conn.execute("DELETE FROM auth_limits WHERE started_at < %s", (now-timedelta(days=1),))
        return True

    def create_session(self, user_id, token, old_token=None):
        now = datetime.now(timezone.utc)
        with self.connection() as conn:
            conn.execute("DELETE FROM app_sessions WHERE expires_at <= %s", (now,))
            if old_token:
                conn.execute("DELETE FROM app_sessions WHERE token_hash=%s", (token_hash(old_token),))
            # Serialize per-user login to bound persistent sessions under concurrency.
            conn.execute("SELECT id FROM app_users WHERE id=%s FOR UPDATE", (user_id,))
            conn.execute("""DELETE FROM app_sessions WHERE token_hash IN
                (SELECT token_hash FROM app_sessions WHERE user_id=%s ORDER BY created_at DESC OFFSET 4)""", (user_id,))
            conn.execute("INSERT INTO app_sessions (token_hash,user_id,expires_at) VALUES (%s,%s,%s)", (token_hash(token), user_id, now+timedelta(hours=1)))

    def session_user(self, token):
        with self.connection() as conn:
            return conn.execute("""SELECT u.id,u.username,u.display_name,u.role FROM app_sessions s
                JOIN app_users u ON s.user_id=u.id WHERE s.token_hash=%s AND s.expires_at>now() AND NOT u.blocked""", (token_hash(token),)).fetchone()

    def revoke_session(self, token):
        with self.connection() as conn:
            conn.execute("DELETE FROM app_sessions WHERE token_hash=%s", (token_hash(token),))

    def revoke_user_sessions(self, user_id):
        with self.connection() as conn:
            conn.execute("DELETE FROM app_sessions WHERE user_id=%s", (user_id,))

    def record_activity(self, user_id, event):
        with self.connection() as conn:
            conn.execute("SELECT id FROM app_users WHERE id=%s FOR UPDATE", (user_id,))
            conn.execute("INSERT INTO activity_events (user_id, payload) VALUES (%s,%s::jsonb)", (user_id, json.dumps(event)))
            conn.execute("""DELETE FROM activity_events WHERE id IN
                (SELECT id FROM activity_events WHERE user_id=%s ORDER BY id DESC OFFSET 100)""", (user_id,))

    def activity(self, user_id):
        with self.connection() as conn:
            return [row["payload"] for row in conn.execute("SELECT payload FROM activity_events WHERE user_id=%s ORDER BY id DESC LIMIT 100", (user_id,)).fetchall()]

    def create_user(self, username, display_name, role, password_hash):
        with self.connection() as conn:
            user_id = str(uuid.uuid4())
            conn.execute("INSERT INTO app_users(id,username,display_name,role,password_hash) VALUES (%s,%s,%s,%s,%s)", (user_id,username,display_name,role,password_hash))
            return user_id

    def change_user(self, username, role=None, blocked=None):
        with self.connection() as conn:
            user = conn.execute("SELECT id FROM app_users WHERE username=%s FOR UPDATE", (username,)).fetchone()
            if not user:
                raise ValueError("User does not exist")
            if role is not None:
                conn.execute("UPDATE app_users SET role=%s WHERE id=%s", (role,user["id"]))
            if blocked is not None:
                conn.execute("UPDATE app_users SET blocked=%s WHERE id=%s", (blocked,user["id"]))
            conn.execute("DELETE FROM app_sessions WHERE user_id=%s", (user["id"],))
