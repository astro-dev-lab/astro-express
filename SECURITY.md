# P1 security boundary

Explicit credential mode disables demo auto-login and rejects insecure HTTP, unapproved origin/host and unsafe database settings. Database startup readiness is required. There are no default production passwords or JWT secrets. User provisioning is local CLI with non-echoing prompts; Argon2id stores salted passwords. Session token digests, one-hour expiry, server-side revocation, persistent login throttles, per-user activity and admin/viewer checks are implemented.

Origin + CSRF safeguards remain. All ASGI response paths carry no-store, CSP, MIME protection, frame denial and no-referrer. Validation/database failures do not echo input or raw errors. Use `--no-access-log --no-proxy-headers` with direct TLS for credential-mode verification to avoid query-string disclosure and untrusted proxy headers. Business deployment requires a separate verified topology and approved target.

P1 tests use synthetic disposable PostgreSQL and temporary local TLS/user credentials. No personal accounts, real customers or vendor sends are exercised. Six provider workflows remain explicitly labeled regression simulations until independent real sandbox evidence and least-scoped secret injection exist. Never put credentials, signing secrets, raw backup archives or environment dumps in Git/chat/issues/logs.

Known limitations: no OS egress firewall; exact dependency pins lack distribution hashes; no automated accessibility conformance claim; no real vendor credential/isolation or signed Stripe sandbox-webhook proof yet. Vercel spending pause and cumulative P1 headroom are unverified. Conditional release is blocked until all CEO gates pass. See `docs/p1-verification.md` and `docs/p1-budget.md`; historical P0 reviews do not certify this head.
