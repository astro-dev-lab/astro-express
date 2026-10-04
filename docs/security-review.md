# SEC-001 independent security review

Reviewed the actual FastAPI and frontend sources on `p0/me-astro-fast-fastapi`, and independently executed checks on 2026-10-03. P0 security gate: **PASS for isolated, single-worker loopback simulation**. This is not production authentication or live integration approval.

## Executed evidence

- `cd backend && .venv/bin/python -m pytest -q`: **36 passed, 1 warning in 3.19s**, exit 0, after dependency upgrades. Warning: current Starlette deprecates HTTPX TestClient in favor of HTTPX2; tests work. The execution environment required network permission for AnyIO local wakeup sockets; default sandbox execution stalled and was interrupted. This permission did not enable application vendor calls.
- `/tmp/astro-sec-audit/bin/pip-audit --no-deps --disable-pip -r backend/requirements.lock --cache-dir /tmp/astro-audit-cache --format json --output docs/evidence/backend-audit-after.json`: exit 0, **No known vulnerabilities found** across 22 pinned packages. Audit tool was separately installed in `/tmp`, not in application dependencies. PyPI advisory lookup uses the network; no vendor credentials or integration APIs are involved.
- `cd frontend && npm audit --json > ../docs/evidence/frontend-audit-after.json`: exit 0, **0 vulnerabilities**, 202 dependencies reported.
- Initial scans are retained in `docs/evidence/*-audit-before.json`: Python reported 16 advisory entries in 2 packages (some duplicated advisory aliases); frontend reported 5 affected packages, including high and critical development-tool findings. Upgraded FastAPI/Starlette/pytest and Vite/Vitest, then rescanned. These scans report known advisories at scan time, not an assurance against unknown flaws.

## Reviewed boundaries

Opaque 256-bit random session cookies replace JWT signing. Cookies are HttpOnly, SameSite=Strict, and Secure for configured HTTPS origins. Login rotates sessions; logout revokes them; expiry, session count and per-session activity are bounded. Every mutation requires an exact configured loopback Origin, rejects cross-site Fetch Metadata, and enforces a 4096-byte actual body limit including streaming bodies. Authenticated mutations also require a per-session CSRF token. Trusted Host middleware rejects non-loopback hosts. Configuration rejects live/production modes, non-loopback origins, credentials, paths and malformed ports. Async endpoints keep in-memory updates atomic within the required single worker.

All six providers use fixed, synthetic fixture logic with random unique demo references. Runtime source imports no vendor SDK or outbound HTTP client; no configured endpoint or live adapter fallback exists. Twelve provider success/failure tests deny `socket.connect`, `socket.create_connection` and DNS resolution. Session history isolation and logout replay are covered. HTTPX exists for tests; OpenTelemetry API is a transitive dependency without an exporter or application instrumentation.

Frontend requests use relative local URLs and same-origin cookies. No external fonts, scripts, analytics, URLs, credential storage or unsafe HTML insertion were found in frontend sources. Normal responses set no-store, CSP restricted to self, frame denial, MIME protection and no-referrer. Early Origin/body rejections return plain text without these response headers; this is a minor hardening opportunity, not an acceptance blocker.

## Cost and remaining limits

No repository `.github` workflow files were present. PMO reported one pre-existing remote dynamic Copilot coding-agent workflow; ordinary development must not invoke or assign Copilot, request cloud workflow runs, merge, or deploy. Package installation/advisory checks and Git handoff are separate from simulated provider flows.

The application does not install an operating-system egress firewall. The source boundary and denied-socket tests verify the implemented provider execution path; browser no-egress evidence is recorded independently by QA. Anyone with local access may enter the fictional operator session, so keep the server on loopback and never use personal data. Python lock versions are pinned but not distribution-hashed. Public hosting, real identities, external provider accounts, infrastructure and repository rename remain fresh CEO gates.
