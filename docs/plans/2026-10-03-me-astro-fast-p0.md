# ME Astro Fast — P0 Implementation Plan

> **For agentic workers:** Execute in small, reviewable tasks; use red/green/refactor testing and preserve evidence for independent QA.

**Goal:** Replace the legacy Express authentication starter with a functional, secure, lightweight FastAPI + web dashboard demonstration of six third-party workflow adapters, without using personal accounts, credentials, billable provider calls, or production infrastructure.

**Architecture:** Python FastAPI serves versioned local APIs and a built frontend. An explicit provider adapter boundary returns deterministic sandbox simulations for Stripe, HubSpot, Notion, Resend, Twilio, and Google; **no outbound provider requests** occur in P0. Authentication and UI operate with synthetic demo identity and local-only state. Real external connections are a separately gated P1 after independent test-account provisioning.

**Tech Stack:** FastAPI, Python 3.12+, Pydantic, pytest, HTTPX TestClient, React + Vite + TypeScript (proposed), local ephemeral SQLite or in-memory demo persistence. Version locks chosen after compatibility verification, not copied from the legacy Node.js dependency tree.

## Global Constraints

- Work in `p0/me-astro-fast-fastapi` only; preserve the legacy `main` branch as recoverable history. No force pushes, branch deletion, or default-branch merges.
- Target repository display name: `me-astro-fast`. Renaming requires GitHub repository Administration access/tool support and is a separate operation; **do not create a second repository just to imitate a rename**.
- Public source must contain no real API keys, billing credentials, personal user data, provider refresh tokens, or actual customer records.
- Stripe, HubSpot, Notion, Resend, Twilio, and Google are fully simulated for P0, with explicit `SIMULATED` labeling in API and UI. **Never claim real vendor certification or live integration tests.**
- No real Stripe charges, emails, SMS, Google API calls, HubSpot or Notion writes, webhooks, provider account creation, infrastructure provisioning, deploys, paid services, workflow reruns, or third-party usage.
- GitHub efficiency: no scheduled workflows; do not enable automatic expensive CI by default; any future approved CI should use path filters, job timeouts <= 10 minutes, least privilege, concurrency cancel-in-progress, and artifacts retained <= 1 day. No external CI providers.
- App is run locally in an isolated environment; mock adapters must be the default and the only available mode at P0. Never fall back to live providers on error.
- Protect against the confirmed legacy JWT-default-secret flaw; no embedded reusable signing secret. Require secure startup configuration for any real authenticated deployment.
- Treat `PMO-001` as the coordination role, `DEV-001` implementation, `SEC-001` threat review, `QA-001` independent verification, `OPS-001` resource review. Role assignments in a document do not mean unattended agents are already running.
- **Human gates:** repository rename, integration test-account connection, public promotion, workflow execution where metered capacity could be consumed, and deployment require fresh explicit CEO approval and recorded evidence.
- No live provider credentials/usage are required to complete the P0 demonstration.

---

### Task 1 — Secure FastAPI core and authentication

**Files (proposed):**
- Create: `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/main.py`, `backend/app/config.py`, `backend/app/auth.py`, `backend/tests/test_auth.py`, `backend/tests/test_health.py`, `backend/.env.example`.
- Existing paths to preserve until migration approved: `src/server.ts`, `src/utils/jwt.ts`, `package.json`.

**Interfaces:**
- `GET /healthz` -> HTTP 200 `{"status":"ok","mode":"simulation"}`.
- `POST /api/auth/demo-login` -> secure local session cookie for synthetic role `demo_admin`.
- `GET /api/auth/me` -> safe `{"user":{"id":"demo-admin","display_name":"Demo Operator","role":"demo_admin"}}` for authorized session; HTTP 401 otherwise.
- `POST /api/auth/logout` -> clears demo session; subsequent access HTTP 401.
- No JWT default/fallback and no real identities. Origin and request-method validation plus CSRF protection for state-changing endpoints; cookies HttpOnly/SameSite and HTTPS Secure flag under protected HTTPS mode.

- [ ] Write focused tests: unauthenticated `/api/auth/me` 401; local login produces session and allows `/api/auth/me`; logout revokes; invalid origin rejected; `/healthz` responds simulation.
- [ ] Run `cd backend && python -m pytest tests/test_auth.py tests/test_health.py -q`; verify failing tests before implementation.
- [ ] Implement FastAPI core and fail-closed config. Ensure demo session secret is generated per process and never logged or committed; production mode must refuse to start without configured strong secrets and HTTPS controls.
- [ ] Re-run focused tests and full `python -m pytest -q`; require all pass before commit.
- [ ] Document startup, exact test results, dependency versions, and security caveats.

### Task 2 — Six offline provider adapters with contract tests

**Files (proposed):**
- Create: `backend/app/integrations/base.py`, `backend/app/integrations/mock.py`, `backend/app/integrations/routes.py`, `backend/tests/test_integrations.py`, `backend/tests/test_no_egress.py`.

**Interfaces:**
- `GET /api/integrations` -> six names, each with `mode:"simulated"`, `connected:false`, and available actions; authorization required.
- `POST /api/integrations/{provider}/simulate` accepts an allowlisted fixture action and returns `{"provider":"...","mode":"simulated","status":"success"|"failed","reference":"demo-..."}`. Invalid provider -> 404, invalid action -> 422, unauthorized -> 401.
- `GET /api/activity` -> mock activity event log scoped to local demo session.
- Provider scenarios: Stripe checkout-success / payment-declined; HubSpot contact-qualified / duplicate; Notion create-page / permission-denied; Resend email-queued / bounced; Twilio SMS-queued / invalid-number; Google calendar-event-created / authorization-rejected. All data synthetic; action results clearly non-real.

- [ ] Add parameterized contract tests for every provider's success and failure fixtures, unauthenticated access, unsupported actions, and result labeling.
- [ ] Make outbound HTTP/socket access impossible inside test suite (network guard), and verify each simulated endpoint passes offline.
- [ ] Implement explicit mock adapter registry, strict Pydantic request/response models, bounded activity history, and no secret environment variables.
- [ ] Run `cd backend && python -m pytest -q` and record six providers x two fixtures, plus auth and no-egress tests.
- [ ] Confirm no provider SDK is invoked and no live provider endpoints are present in the P0 execution path.

### Task 3 — Functional responsive dashboard

**Files (proposed):**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/src/App.tsx`, `frontend/src/main.tsx`, `frontend/src/styles.css`, `frontend/src/api.ts`, `frontend/src/App.test.tsx` (and lockfile on first reproducible install).

**Interfaces:**
- Sign in as fictional Demo Operator -> fetch `/api/auth/me`; sign out revokes session; protected dashboard renders six adapters with clear `SIMULATION — NO LIVE CONNECTIONS` banner.
- Six provider cards expose at least one success and one failure scenario each; invoke backend API and show returned status/reference. Activity list refreshes from `/api/activity`; show loading, access denied, network failure, and unknown provider errors.
- Responsive navigation, keyboard focus visibility, semantic labels, and no outbound analytics or third-party font fetch.

- [ ] Write frontend tests for unauthenticated view, login, all six cards, example run, error response and sign-out.
- [ ] Verify tests fail before behavior exists, then implement smallest functional UI.
- [ ] Run `npm ci && npm test -- --run && npm run build` in `frontend`; exact scripts to be committed.
- [ ] Verify a local browser smoke run: login, each card, history, logout, mobile layout; attach screenshots only if from actual browser run.
- [ ] Wire built static frontend into FastAPI locally without any cloud deployment.

### Task 4 — Security, documentation, cost controls and proof

**Files (proposed):**
- Create: `README.md` replacement on branch, `docs/architecture.md`, `docs/verification.md`, `docs/integrations.md`, `SECURITY.md`, `.dockerignore`, `backend/Dockerfile` (if local container packaging used).
- Retain original source history to permit migration review; only remove legacy Express files **on the development branch** after replacement passes.

- [ ] Run reproducible backend tests, frontend tests, TypeScript build, and lint/typecheck as defined by committed scripts. Capture exit codes and output.
- [ ] Audit for secrets, hard-coded real credentials, development-server exposure, CORS/CSRF issues, dependency advisories, unsafe containers, and outbound network behavior. Do not claim vulnerability scanning without a real scan.
- [ ] Replace unverified README production claims, invented customer success stories, coverage badges, and paid product assertions with verified facts.
- [ ] Provide clear local-only demonstration instructions and mode warning. Prove that all six adapters function **in simulation**, not against live accounts.
- [ ] Open draft PR `p0/me-astro-fast-fastapi` -> `main` containing evidence and findings. Do not merge.
- [ ] QA-001 issues PASS/FAIL/BLOCKED against evidence; SEC-001 verifies critical findings; CEO reviews rename/publication gate separately.

## Handoff, authority, and acceptance

**PMO-001:** single accountable coordinator; break work into bounded implementation tasks, delegate complex environment work to Codex only after a registered Codex environment is available. Avoid claiming autonomous subagents were started merely by listing roles.

**P0 acceptance** requires an actually runnable local demo with:
1. A FastAPI `/healthz` service and protected demo-login/dashboard/logout flow.
2. Six offline mock integrations with success + failure scenarios and audit history.
3. A responsive UI consuming actual local FastAPI endpoints.
4. Backend/frontend test logs, explicit no-egress verification, and no known critical auth regressions.
5. Clearly labeled simulation, no external account connections, no billing activity, and a reviewable draft PR.

**P1 (NOT authorized by this packet):** Independent nonpersonal vendor test accounts, API-key setup, actual vendor sandbox contract runs, provider webhooks, live OAuth, message delivery, production billing and deployment. Each integration separately gated by CEO.

## Open external decisions (not blockers for P0 simulation)

- Repository rename cannot be performed through the connected GitHub tools; requires authorized GitHub repository Administration action.
- Codex Tasks currently reports no registered environments; delegation blocked until environment connection.
- Actual vendor integration and deployment cannot be marked certified until CEO approves separate test-account usage and independent verification.
