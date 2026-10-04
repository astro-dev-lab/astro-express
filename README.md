# ME Astro Fast — P1 foundation

Canonical repository **astro-dev-lab/me-fastapi**, repository ID `1109489408`. The former `astro-dev-lab/astro-express` URL redirects to this same repository; its rename occurred outside this task. Work is on `p1/minimum-production-foundation` from approved main `b0455158633806a32bf7a401b7e2b225667f8b8b`.

P1 adds credential authentication, administrator/viewer authorization, PostgreSQL-backed revocable sessions and activity, explicit migrations, safe logs and health checks. The existing six-card dashboard remains. Its twelve provider actions are **regression fixtures**, not real vendor operations. Cards say SIMULATED / NOT CONNECTED; credential mode additionally says SANDBOX NOT CONFIGURED. Real provider testing is authorized but **BLOCKED** pending approved accounts and secure credential injection. See [P1 evidence and release gates](docs/p1-verification.md) and [budget ledger](docs/p1-budget.md).

## Install and local regression mode

Python 3.12+ and Node.js 22+:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock
npm --prefix frontend ci
npm --prefix frontend run build
./scripts/run-demo.sh
```

Open http://127.0.0.1:8000. This explicitly local, no-credential mode has temporary sessions and fixture-only activity. It is not production login. Built assets are served by FastAPI; no third-party fonts, analytics or provider requests are needed.

## Credential mode with PostgreSQL

Use an approved local PostgreSQL database; provision its role/database separately with least privileges. No seeded app user/password exists. Configure `DATABASE_URL` through an approved process environment, never Git/chat/logs. The P1 driver accepts only explicit loopback PostgreSQL destinations and rejects libpq host/service/options overrides. Remote/cloud database connections require a separately verified target and corresponding scoped configuration change.

```bash
cd backend
../.venv/bin/python -m app.migrate up
../.venv/bin/python -m app.provision create-user operator --role admin --display-name 'Administrator'
../.venv/bin/python -m app.provision create-user observer --role viewer --display-name 'Viewer'
cd ..
```

Provisioning requires an interactive terminal with non-echoing password prompts (16–256 characters); passwords are never command arguments or seeded defaults. Database credentials remain injected. `set-role`, `block-user`, `unblock-user`, and `revoke-sessions` CLI commands revoke affected sessions. The browser offers no public registration.

Select credential mode explicitly with `APP_MODE=production`, `APP_ORIGIN` equal to the exact HTTPS origin, `PRODUCTION_ACK=I_ACCEPT_PRODUCTION_SECURITY_REQUIREMENTS`, and injected `DATABASE_URL`. There is no JWT default or shared signing secret: random opaque session tokens are stored only as SHA-256 digests. Users have salted Argon2id hashes. The production acknowledgement is a safety switch, not a credential.

Start on loopback with approved TLS certificate/key paths and access logging disabled:

```bash
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8443 --workers 1 --no-access-log --no-proxy-headers --ssl-certfile /approved/path/certificate.pem --ssl-keyfile /approved/path/private-key.pem
```

Do not create real keys from the sample paths. Local QA generates a disposable self-signed certificate only in a private temporary directory. For a future proxy deployment, explicitly review TLS termination and forwarded-header trust before changing the runtime flags. Current deployment is not configured.

Credential mode fails startup if PostgreSQL/migration state is unavailable; it rejects HTTP and disables demo auto-login. Administrators can execute fixtures; viewers can read their own activity/cards and log out. Session expiry is one hour, login attempts are throttled in PostgreSQL, and role/block changes are checked on protected access. All responses, including errors/early rejections, carry security headers. `/healthz` is liveness; `/readyz` returns 503 when the database is unavailable. Logs use allowlisted JSON events without credentials, users, request/query strings or raw database errors.

## Verification

```bash
cd backend
../.venv/bin/python -m pytest -q
cd ../frontend
npm test -- --run
npm run typecheck
npm run build
```

Without PostgreSQL the four real integration tests are skipped, which does not prove persistence. With an explicitly disposable local database named `astro_test_*`, inject `TEST_DATABASE_URL` and exact `TEST_DATABASE_CONFIRM`, then rerun backend tests. Those tests apply and tear down schema; never point them at business data.

[Local PostgreSQL/backup instructions](docs/p1-postgres.md) reproduce the tested disposable container and runtime/restore verification. P1 evidence includes **81 backend tests with real PostgreSQL and zero skips**, **9 frontend tests**, real HTTPS process restart, browser credential login/RBAC and backup/restore. Prior P0 reports in `docs/verification.md`, `docs/qa-report.md` and `docs/security-review.md` are historical, not P1 certification.

## Release and provider gates

CEO permits conditional merge/deployment under a cumulative **USD $200** ceiling. They require exact-head independent QA/SEC, actual database proof, builds/isolation checks, reconciled costs/headroom and an identified deployment owner/target. Costs and provider access remain unreconciled, so no merge/deployment has occurred. Vercel Pro credits are not a hard spend cap. No Actions, scheduled workflow, live customer operations or additional repository rename is enabled.

MIT; see [LICENSE](LICENSE).
