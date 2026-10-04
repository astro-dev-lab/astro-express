"""Unit-only fake repository. Not PostgreSQL integration or persistence proof."""
from collections import defaultdict
import time
from app.auth import hash_password, token_hash
from app.store import StoreUnavailable

PASSWORD = "synthetic-test-password-123"

class FakeStore:
    def __init__(self):
        self.users = {name: {"id": identifier, "username": name, "display_name": name.title(), "role": role,
                           "blocked":False, "password_hash": hash_password(PASSWORD)}
                      for name, identifier, role in [("admin", "00000000-0000-0000-0000-000000000001", "admin"),
                                                     ("viewer", "00000000-0000-0000-0000-000000000002", "viewer")]}
        self.sessions = {}
        self.events = defaultdict(list)
        self.attempts = defaultdict(int)
        self.available = True

    def ready(self):
        if not self.available:
            raise StoreUnavailable("synthetic-secret-must-not-leak")
        return True

    def user_by_username(self, username):
        self.ready()
        return self.users.get(username)

    def allow_login_attempt(self, username):
        self.ready()
        self.attempts[username] += 1
        return self.attempts[username] <= 5

    def create_session(self, user_id, token, old_token=None):
        self.ready()
        self.sessions.pop(token_hash(old_token or ""), None)
        self.sessions[token_hash(token)] = (user_id, time.time()+3600)

    def session_user(self, token):
        self.ready()
        session = self.sessions.get(token_hash(token))
        if not session or session[1] <= time.time():
            return None
        return next((u for u in self.users.values() if u["id"] == session[0] and not u["blocked"]), None)

    def revoke_session(self, token):
        self.ready()
        self.sessions.pop(token_hash(token), None)

    def revoke_user_sessions(self, user_id):
        self.ready()
        self.sessions = {key: value for key, value in self.sessions.items() if value[0] != user_id}

    def record_activity(self, user_id, event):
        self.ready()
        self.events[user_id].insert(0,event)
        self.events[user_id] = self.events[user_id][:100]

    def activity(self, user_id):
        self.ready()
        return self.events[user_id]
