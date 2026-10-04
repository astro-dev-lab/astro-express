# ME Astro Fast

A local FastAPI dashboard for exploring six **simulated** workflows. Stripe, HubSpot, Notion, Resend, Twilio, and Google have no account connections. No payments, messages, CRM changes, workspace writes, OAuth, or calendar writes occur.

Canonical repository: `Astro-dev-lab/astro-express`; branch: `p0/me-astro-fast-fastapi`. Repository renaming is deferred. The legacy Express application remains recoverable on `main` and in Git history.

## Install and run

Requires Python 3.12+ and Node.js 22+. From the repository root:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

After installation/build, `./scripts/run-demo.sh` starts the same single-worker loopback server with the canonical local origin.

For frontend development only, start the backend with `DEMO_ORIGIN=http://127.0.0.1:5173` and run `npm --prefix frontend run dev`. Open that exact Vite origin; its API proxy uses the backend on port 8000. The built demo needs only the single FastAPI server.

Open **http://127.0.0.1:8000** and select the synthetic demo session. Run either outcome on each card; the API returns a uniquely referenced simulated result and records it in your session history. Sign out to revoke the session. State is temporary and is discarded on logout, expiry, or restart.

Installation downloads free open-source packages. After installation/build, startup needs no external services, credentials, databases, or internet. Keep the server on loopback, use one worker, and use the exact configured origin. This login selects a fictional operator; it is not identity verification and must never protect real data. Production and live provider modes are unsupported and fail closed. See [security](SECURITY.md) and [architecture](docs/architecture.md).

## Verify locally

```bash
cd backend
../.venv/bin/python -m pytest -q
cd ../frontend
npm test -- --run
npm run typecheck
npm run build
```

The independent [QA report](docs/qa-report.md) and [verification evidence](docs/verification.md) describe actual checks and limits. Browser testing uses local Chromium; no hosted testing or GitHub Actions execution is required.

All six providers offer deterministic success and failure fixtures with synthetic data. Every card and API result identifies simulation; none is connected. See [fixture catalog](docs/integrations.md). No third-party fonts, analytics, provider SDKs, or vendor URLs are needed at runtime.

P0 uses local tests only: no scheduled workflows, automatic CI/deploy, infrastructure provisioning, or paid resources. CEO review gates merge, repository rename, public promotion, deployment, and future live integrations. This is a demonstration with no production-readiness or customer certification claim.

MIT licensed; see [LICENSE](LICENSE).
