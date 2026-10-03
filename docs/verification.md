# PMO-001 P0 acceptance evidence — 2026-10-03

Canonical workspace `/workspace/astro-express`, branch `p0/me-astro-fast-fastapi`. Plan baseline `774d0d963118441d8cd7145bc6cb2ac672d5f62f`. Local `main` remains `89771d024e43033fc32af059cc7b718b9a0b0de0`.

PMO coordinated actual DEV backend/frontend and independent QA/SEC subagents in this workspace. No remote Codex Tasks process, task ID, autonomous external environment, or Copilot execution is claimed. See [QA](qa-report.md) and [security review](security-review.md) for independent findings.

| Gate | Actual result | Evidence |
|---|---|---|
| Isolated Python lock install | Exit 0; `pip check` clean | `evidence/backend-install.txt` |
| Backend pytest | 36 passed, 0 failed; 1 upstream TestClient deprecation warning | `evidence/backend-tests.txt` |
| Reproducible frontend `npm ci` | Exit 0 | `evidence/frontend-install.txt` |
| Frontend tests | 4 passed, 0 failed | `evidence/frontend-tests.txt` |
| TypeScript typecheck | Exit 0 | `evidence/frontend-typecheck.txt` |
| Production frontend build | Exit 0; 30 modules; JS 193.69 kB / 61.49 kB gzip; CSS 7.70 kB / 2.38 kB gzip | `evidence/frontend-build.txt` |
| Independent Chromium smoke | 25 checks passed, 0 failed; 0 external browser requests; 0 JavaScript errors | `evidence/browser-smoke.txt`, desktop/mobile PNGs |
| Backend dependency audit | 0 known vulnerabilities in 22 pins | `evidence/backend-audit-after.json` |
| Frontend dependency audit | 0 known vulnerabilities in 202 reported dependencies | `evidence/frontend-audit-after.json` |
| Root runtime smoke | `/healthz` 200 with `{"status":"ok","mode":"simulation"}`; dashboard `/` HTTP 200 | Root curl execution after browser QA |

Commands: root `.venv/bin/python -m pip install -r backend/requirements.lock`; `cd backend && ../.venv/bin/python -m pytest -q`; `cd frontend && npm ci && npm test -- --run && npm run typecheck && npm run build`. Logs retain actual stdout. Advisory lookup contacted free package registries, not integration vendors. Browser test uses installed Python Playwright and `/usr/bin/chromium`, with the local server running; reproduce using `python scripts/qa-browser.py` in an environment that already provides those optional QA tools.

Verified runtime: keyboard demo login; six cards explicitly SIMULATED/NOT CONNECTED; all twelve success/failure fixtures; unique demo references; per-session history; second-session isolation; logout and old-cookie replay rejection; empty new-session history; 390px mobile and 1440px desktop layouts; 403 and network-error recovery. Provider tests replace socket connect/connection/DNS with a denial guard while executing all twelve fixtures. Source review found no vendor clients, SDKs, endpoints, analytics, external fonts, or live fallbacks in the P0 execution path.

Initial dependency scans found advisories and prompted patched locks; before/after reports are retained. Initial normal Rollup builds stalled; the isolated diagnosis showed treeshaking as the trigger. The committed `treeshake: false` setting builds reliably with the pinned toolchain; no claim is made that the upstream root cause is proven. JSX/TypeScript source is readable and production assets are locally generated, not committed. Default sandbox TestClient/browser execution lacked local socket/process capability; approved local-only escalations allowed verification. Stalled processes were stopped. No valid failing behavior baseline was recorded before implementation; do not infer test-first development from the final green runs.

After replacement tests/build and browser QA passed, legacy Express source/manifests, Prisma/database setup, and Docker deployment paths were removed on this development branch. They remain in `main` and history. Unsupported README production/customer/premium claims were replaced with verified demo scope.

No critical P0 QA/security blocker remains. Limits: synthetic login is not real identity verification; one loopback worker and volatile state only; no OS egress firewall; version pins are not distribution hashes; one upstream TestClient warning. Automated accessibility conformance, live providers, production authentication and hosting are not certified.

GitHub efficiency: no repository workflow files, scheduled jobs, CI/deploy configuration, provisioning, caches or artifact uploads were added. Read-only GitHub inspection found one pre-existing dynamic Copilot-agent workflow, never invoked. Branch rules only prohibit deletion/non-fast-forward updates. Requested draft PR and issue #2 handoff use ordinary GitHub metadata operations, without assigning Copilot or requesting Actions. Estimated P0 Actions runner use: 0 minutes; no workflow execution was requested.

Next CEO gate: review independent QA/SEC evidence and the draft PR, then decide on merge. Repository rename, public promotion, deployment, cloud workflows and live provider connections remain separate approvals. No merge, deployment, rename, account creation, messages, CRM writes, payments or Google sign-in occurred.
