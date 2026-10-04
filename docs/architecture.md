# P0 architecture

FastAPI serves a built React/TypeScript dashboard and same-origin `/api` routes. Vite is a local build tool. Runtime needs neither Node nor PostgreSQL. One loopback-bound Python process owns temporary demo sessions and bounded activity histories.

Demo login creates a random opaque session cookie and a separate CSRF token. The browser sends cookies on local API requests and the CSRF header on protected mutations. Login validates Origin even though no session exists yet. Logout revokes server state. No JWT signing secret, password, personal identity, or vendor credential is involved.

Provider IDs and fixture actions are allowlisted. A pure simulation registry maps each fixture to a fixed synthetic outcome; each invocation receives a new demo reference. Failure fixtures are successful HTTP deliveries of a simulated failure, distinct from invalid inputs, authentication failure, and network errors. No runtime code path connects a vendor.

Restart intentionally revokes all sessions. Multiple workers, shared deployments, production authentication, durable data, and live providers are outside P0. Configuration rejects unsupported modes instead of falling back to a live adapter.

The legacy starter is preserved in Git history and `main`; P0 removes its executable path after the replacement passes. Rollback uses ordinary Git history without copying or moving the repository.
