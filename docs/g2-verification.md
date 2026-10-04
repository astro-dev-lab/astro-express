# G2 verification and review handoff

G2-only branch `g2/corporate-factory-mvp`, based on P1 reviewed head `26ee7b120bffd4d710ea7d3fcd12ee60c2c9b0ac`; one draft PR stacked against `p1/minimum-production-foundation`. Source, tests, evidence and incremental budget are separate from P1. No P1 branch/PR mutation, main update, merge, deployment, Actions, factory label, live vendor call or new paid resource is authorized by this handoff.

## Executed commands and outcomes

| Check | Command | Result |
|---|---|---|
| Tests-first contract boundary | `.venv/bin/python -m pytest -q backend/tests/test_corporate.py` | Initial missing module collection error exit2, then 12 passed exit0 |
| Tests-first schema fail-closed behavior | actual-Pg `pytest -q tests/test_corporate_postgres.py -k unknown_schema` | 1 failed + teardown error exit1: unexpected version0 was not rejected by runtime readiness; minimal exact-version-list fix then full green |
| P1+G2 backend final | `TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55433/astro_test_g2 TEST_DATABASE_CONFIRM=astro_test_g2 ../.venv/bin/python -m pytest -q` in backend | 106 passed, 0 failed, 0 skipped, exit0; one upstream Starlette TestClient warning |
| Actual G2 PostgreSQL tests | same environment, `pytest -q tests/test_corporate_postgres.py` | 13 passed (included in 106); P1 four actual-Pg tests also run |
| Frontend | `npm --prefix frontend test -- --run` | 14 passed (9 unchanged P1 + 5 G2), exit0 |
| Types/build | `npm --prefix frontend run typecheck`; `npm --prefix frontend run build` | exit0 both; 32 modules, JS204.15KB / gzip64.52KB, CSS9.93KB / gzip2.89KB |
| Actual TLS/Pg/browser/restart | installed-Python wrapper for `scripts/verify-g2-runtime.py` in [setup](g2.md) | 6 checks passed, all12 P1 fixtures, actual process restart, authenticated durable Corporate records, mobile/keyboard, no duplicate marker, logout, zero outside-origin browser requests/JS errors |
| Wheel packaging tests-first | existing global Python `pip wheel --no-index --no-deps --no-build-isolation ... ./backend`, archive assertions | First built wheel omitted Corporate SQL, assertion exit1; package-data-only fix then exact Corporate/P1 SQL archive checks passed exit0 |
| Source whitespace/syntax | `git diff --check`; `python -m compileall -q backend/app/corporate.py scripts/verify-g2-runtime.py` | exit0 |

No dependency version or lockfile changes. Wheel archive verification uses already installed global setuptools84; pinned isolated build backend82 is not installed in the virtualenv, so no reproducible locked-wheel-environment claim is made. No build dependency was downloaded or installed. Container-image vulnerability scanning was not performed. Existing P1 dependency scans are historical evidence, not a newly executed G2 scan.

[Genuine logs](evidence/g2) retain initial failures separately; trailing whitespace/blank EOFs were normalized without changing results. `backend.txt` is the earlier 105-pass checkpoint; `backend-final.txt` is final106. `postgres-api.txt` is an earlier 11-test database checkpoint, not final13. First frontend collection failed because the new component did not yet exist; this is not falsely described as a behavioral assertion failure. Actual schema/wheel failures are behavioral/artifact checks. A preliminary `.venv` wheel attempt could not import setuptools; no artifact/pass claimed. Global installed tooling then performed the red/green archive proof.

## Independent reviewers

Actual isolated reviewer agents `/root/g2_qa` and `/root/g2_security` performed source review without changing source or branches. Database execution slots were sequential and used only the disposable G2 synthetic database, so concurrent destructive setup could not interfere. These are model review sessions, not human employees or fabricated autonomous staff.

- QA independently ran full actual-Pg suite105 before the final no-egress test, then G2 suites25 after its addition; frontend and browser checks independently passed. QA identified expiry UX ambiguity; explicit fresh-intake guidance and hidden expired contract actions resolved it.
- SEC independently ran full final actual-Pg suite106 (0 skips), including13 G2 database tests; reviewed owner/session/Origin/CSRF, repository binding, service-principal denial, transaction/idempotency/budget, logging/no credentials, SQL append-only triggers, package-data and live-blocked boundary. No unresolved critical/high finding in the local contract MVP.
- Both reviewers initially encountered restricted local execution (a stalled/default-sandbox attempt or DB setup errors); those attempts were stopped, not counted as pass. Their permitted local execution commands completed and were reported separately.

Exact final commit attestation and reproducible independent results are attached to the stacked draft PR after the commit is fixed. A source change after attestation requires a new reviewed head. Reviewers do not approve their own implementation or grant CEO production authorization.

## Blockers and limitations

Actual Foreman issue/label/run testing is **BLOCKED** until upstream trigger authorization enforces the owner/digest/expiry/budget gate. Verified source at `eve-software-factory-template` SHA47a0f4ca shows a raw trusted-label trigger; deployed installation identity is unverified. Contract jobs are marked `BLOCKED_UPSTREAM_AUTHORIZATION`; marker strings are not real GitHub issues. No bot ingress or credentials enabled. Live connector uncertain-response reconciliation is future gated work, not proved by deterministic markers.

The append-only SQL guard trusts database administrators; secret-pattern rejection is not complete secret detection. Expired approvals require fresh intake; lists are bounded100 without pagination. Account provisioning is local/operator-only, no seeded password. Corporate unavailable in demo; production-mode app here is only local TLS test configuration. No actual production service, remote DB, external budget reconciliation, backup/RPO SLA or live provider certification is claimed.

G2 new paid-spend ceiling remains0. Task initiated no paid provider/provisioning action or subscription; cached local DB tooling required no download or remote service. Managed workspace/model/account overhead invoice was not supplied. Do not claim P1 funds or unknown existing charges as G2 headroom. No merge/deploy/run trigger is permitted.
