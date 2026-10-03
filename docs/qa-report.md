# QA-001 independent P0 verification

Date: 2026-10-03 UTC. Branch: `p0/me-astro-fast-fastapi`. QA ran commands independently against the implemented demo; no vendor accounts, cloud browser, deployment, or GitHub workflow was used.

## Gate result: PASS for isolated local simulation

| Gate | Actual outcome | Evidence |
| --- | --- | --- |
| Backend pytest | 36 passed, 0 failed; 1 Starlette/httpx deprecation warning | `evidence/backend-tests.txt` |
| Frontend Vitest | 4 passed, 0 failed | `evidence/frontend-tests.txt` |
| TypeScript | `npm run typecheck`, exit 0 | `evidence/frontend-typecheck.txt` |
| Production asset build | `npm run build`, exit 0 | `evidence/frontend-build.txt` |
| Real local Chromium smoke | 25 checks passed, 0 failed | `evidence/browser-smoke.txt` |

The server was started with `backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000`. Chromium visited the built frontend through this same FastAPI origin. The smoke script is `scripts/qa-browser.py`; it requires the separately installed Python Playwright package and `/usr/bin/chromium` available in this QA environment.

## Runtime verified

The smoke independently asserted the plan's twelve explicit fixtures: Stripe checkout success/payment declined, HubSpot contact qualified/duplicate, Notion create page/permission denied, Resend email queued/bounced, Twilio SMS queued/invalid number, Google calendar event created/authorization rejected. All returned HTTP 200 with their expected simulated success/failed status, `connected:false`, a unique `demo-` reference, and matching UI result/history. The page showed six cards with SIMULATED and NOT CONNECTED badges.

Keyboard Tab/Enter login worked. Actual browser session cookies were HttpOnly and SameSite Strict. An unauthenticated valid mutation returned 401. A second browser session had empty history. Logout returned to login, revoked server access, and rejected replay of the old cookie; a new session started empty.

At desktop 1440px and mobile 390px, the dashboard had no horizontal overflow. Mobile action/signout buttons measured at least 44px high. Pending simulation displayed Running and disabled action/signout controls; controls reenabled after completion. Injected local 403 and aborted local requests displayed appropriate alerts and recovered controls. Actual screenshots: `evidence/dashboard-desktop.png` and `evidence/dashboard-mobile.png`.

The browser route guard blocked any request outside `127.0.0.1:8000`: zero external requests were observed, and zero JavaScript page errors occurred. Backend tests exercised all twelve fixture flows while blocking socket connect/create_connection and DNS resolution. These are simulation/no-egress checks, not live-vendor contract tests or a full operating-system packet capture.

## Environment findings and limits

The restricted process sandbox stalled FastAPI TestClient and initially prevented Chromium launch (crashpad `setsockopt: Operation not permitted`). Approved local-only execution outside that process sandbox completed tests and browser verification. Earlier Vite tree-shaking builds stalled; the frontend owner disabled tree shaking explicitly for this small demo and the final build passed. Intermediate missing executable errors came from concurrent dependency installation; settled locked installation passed.

The remaining test warning concerns deprecated Starlette TestClient use of httpx; it is not a test failure. Sessions are process-memory state and disappear on restart. Demo login uses synthetic identity and offers no production authentication. A separate browser dependency is intentionally not part of the app runtime lock. No critical QA blocker remains for the isolated simulation scope; security assessment is recorded separately by SEC-001.

CEO gate: review the draft handoff and authorize any later publication, repository rename, deployment, workflow execution, real account connections, or live-provider use separately. None occurred during QA.
