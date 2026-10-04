# P1 WP-01–WP-04 evidence and conditional release status

Date 2026-10-04. Canonical `astro-dev-lab/me-fastapi`, repository ID `1109489408`; former name redirects to the same repository. The rename occurred externally. Checkout remains `/workspace/astro-express`; branch `p1/minimum-production-foundation`; approved baseline `b0455158633806a32bf7a401b7e2b225667f8b8b`. Canonical repository ID and remote main/P1 baseline were read and matched before synchronization. No second branch/repository/project was created.

## Actual final executions

| Gate | Coordinator execution | Independent evidence |
|---|---|---|
| WP-01 all response hardening | Test-first: **3 failed / 3 passed**, then **42 passed** after outer-ASGI fix | QA/SEC independently checked rejections; SEC also probed normal 200, method 405, unhandled 500 |
| Final backend with actual PostgreSQL | **81 passed, 0 failed, 0 skipped**, one upstream TestClient warning; 11.29s | QA independently **81 passed, 0 skipped**, 13.34s |
| Frontend credentials/viewer/sandbox-state | **9 passed**, 2.86s; initial credential UI **3 failed / 4 passed** and sandbox state **1 failed / 8 passed** | QA independently **9 passed**, 2.44s |
| Typecheck and build | Exit 0; build 30 modules, 863ms; JS gzip **62.04 kB**, CSS gzip **2.46 kB** | QA independently typecheck exit 0, build 1.61s |
| Existing local dashboard browser | Twelve fixtures/keyboard/mobile/errors/loading/isolation/logout | QA independently **25 checks passed**, zero external requests/JS errors; screenshot writes suppressed |
| Real PostgreSQL integration | Four actual DB tests included in the 81-test suite | QA independently **4 passed**, 1.58s |
| Real credential TLS/app restart/restore/browser | **7 checks passed**; root initial harness issues corrected and failures retained | QA independently final strengthened script **7 passed**, including restored usable session token |
| Dependencies | `pip check` clean; exact 28 Python pins and existing npm lock | SEC actual audits: **0 known vulnerabilities** in 28 Python pins / 202 npm dependencies |
| Actual PostgreSQL outage/recovery | **4 checks passed**, paused only owned test DB | QA independently **4 passed**, hardened readiness/login 503, liveness/recovery 200 |
| Real vendor tests | **BLOCKED**, no successful real account operation executed | Fixtures explicitly excluded from provider acceptance |

Logs: `docs/evidence/p1/` retains root executed stdout, red baselines, final backend/frontend/build outputs, dependency audit JSON and unsuccessful local harness attempts. Trailing whitespace in text logs is normalized only for Git review. Independent reviewer outputs are summarized here from their actual tool executions; exact-head attestations are recorded in the draft PR after final commit, rather than embedding a self-referential SHA into this file.

Commands: `cd backend && TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/astro_test_p1 TEST_DATABASE_CONFIRM=astro_test_p1 ../.venv/bin/python -m pytest -q`; `cd frontend && npm test -- --run && npm run typecheck && npm run build`. `scripts/verify-p1-postgres.py` plus the wrapper in `docs/p1-postgres.md` executes TLS/runtime/browser/backup proof. Local optional Playwright/system Chromium are present; no hosted browser used.

## What is proved

WP-01: CSP/no-store/frame/MIME/referrer hardening applies at the outer ASGI boundary, including early Origin/cross-site/size 403/413, host 400, auth 401, 404/405 and 500. Origin and CSRF enforcement remain. Production-capable mode requires explicit HTTPS origin, acknowledgement and validated loopback PostgreSQL; demo auto-login is disabled. Invalid/missing modes/origins/DB configuration fail closed.

WP-02: Argon2id salted password verification; no public registration/seeded production password; CLI provisioning via non-echoing terminal; PostgreSQL-backed opaque session digests, one-hour expiry, logout/revocation, account/global throttles and current blocked/role checks. Admin can mutate fixtures; viewer reads scoped data and can log out. Tests cover bad credentials, blocked users, expiry, role changes, logout replay and admin session revocation. Validation responses/logs exclude credential inputs. Actual HTTPS browser verified credential login, viewer-disabled actions, mobile layout and logout against real PostgreSQL.

WP-03: PostgreSQL users/roles/sessions/activity/login limits through parameterized SQL, version-1 migrations with transactional advisory locking, idempotent upgrades and confirmed `astro_test_*`-only downgrade. Actual database tests ran successfully. Sessions/activity survived a real Uvicorn process termination/restart, not only a new repository object. Four tests were initially skipped when PostgreSQL was absent, then executed after the CEO resource amendment enabled a free disposable local test container.

WP-04: fixed-field JSON logs, generic validation/driver failures, independent liveness and DB/schema readiness, TLS-only credential runtime, disabled access/proxy-header logs, synthetic `pg_dump`/`pg_restore` round trip. Restored schema, password verification, usable session token and twelve history entries passed. DB-down readiness/login 503 and liveness 200 were tested both with labeled unit fakes and by pausing the actual owned PostgreSQL container; readiness recovered after unpause. Root and independent QA each passed all four actual-outage checks. No fake result is claimed as real DB outage evidence.

## Implementation/test findings

Default validation 422 initially echoed an unexpected credential-adjacent input; a focused test exposed it and the handler now returns generic `Invalid request`. Libpq override environments could bypass local URI intent; destination/options overrides are rejected and the driver pins numeric loopback hostaddr. Structured logging was enabled with fixed fields; production access logs are disabled to avoid query-string disclosure.

Initial Docker internal-network tests failed with connection refused (76 passed / 4 errors); that network did not publish ports. A normal bridge retained loopback-only binding and passed actual tests. Initial runtime test harness used too-short graceful shutdown, then failed pg_restore because Docker stdin was not forwarded; corrected timeout and `docker exec -i` produced the final seven passes. Failure logs are retained. These failures are not silently reported as passes. No backups, temporary TLS private keys or generated synthetic passwords are committed.

## Independent gates and remaining blockers

QA performed actual 81-test/backend, 9-test/frontend, 25-check regression browser, four-Pg integration seven-runtime/backup and four actual-outage checks. SEC independently reviewed security headers/auth/RBAC/SQL/session/error/log controls and executed dependency audits and local tests. Reviewers edited no implementation source. Source/tests and final proposed SHA must remain identical to their exact-head attestation; any later change requires appropriate fresh review.

Remaining constraints: six real sandbox tests and signed Stripe sandbox-webhook evidence are BLOCKED without verified authorized test accounts and secure injection; cumulative incurred charges/commitments/taxes and remaining $200 headroom are UNKNOWN; Vercel target/owner, incremental costs and spend PAUSE are unverified. No cloud DB or Vercel project was provisioned/linked. Production business DB least privilege/backup policy/TLS topology are not certified by disposable local tests. No OS egress firewall or automated accessibility conformance claim; version pins lack distribution hashes; one TestClient deprecation warning.

**Conditional release gate: BLOCKED.** CEO merge/deployment permission is conditional, not an automatic publish instruction. Actual local foundation proof now passes, but cost/target/provider-security prerequisites remain unresolved. No merge, deployment, Actions run, schedule, live customer operation or additional rename occurred. No Eve/Foreman control plane, tenancy, Redis, ORM, identity provider or six speculative SDKs were added. See budget/provider documents for precise next inputs.
