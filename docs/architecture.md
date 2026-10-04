# P1 architecture

A single FastAPI application serves the existing built React/TypeScript dashboard. Default loopback simulation mode remains for regression use. Explicit production-capable mode requires an HTTPS origin, acknowledgement and approved local PostgreSQL; startup checks schema readiness and never auto-migrates. There is no live deployment or remote DB target configured.

PostgreSQL schema version 1 contains users (admin/viewer, blocked flag, Argon2id hashes), opaque session digests/expiry, per-user JSON activity and persistent login limits. Parameterized SQL uses psycopg; no ORM, Redis, tenancy or identity provider was added. Migration transactions use an advisory lock; an idempotent upgrade and disposable-only confirmed downgrade are explicit CLI operations.

Authentication returns a Secure/HttpOnly/SameSite=Strict opaque session cookie and derived CSRF token. Origin/body limits protect mutations; session/role/block checks come from the database. Logout and administrative revocation delete sessions. Activity and sessions survive actual app-process restarts. Reads are scoped to the authenticated user. Provider actions continue to be deterministic regression fixtures and stay labeled simulated/not connected; no vendor clients or credentials are loaded.

Hardening wraps the outer ASGI response boundary, including early rejections and 500 responses. Validation errors omit input values; driver failures return generic 503 and fixed-field JSON events. Production runtime disables Uvicorn access logs and proxy-header inference. Liveness is independent of DB; readiness checks schema/database.

The local test PostgreSQL container is non-root, read-only with tmpfs data, capability-free, resource-bounded and publishes only loopback. Its normal bridge permits outbound connectivity; it is not an OS egress firewall. Application fixture socket-denial and browser request checks prove the reviewed execution paths, not arbitrary future code. Temporary test credentials/keys/backups are not committed. Real sandbox testing and release remain gated by verified accounts, secret injection, cost headroom and target ownership.
