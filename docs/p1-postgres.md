# Disposable local PostgreSQL, migration and restore proof

These commands create only a **synthetic test** database/container. They are not deployment instructions. Never point the integration tests or downgrade at business data. The public official image has no provider fee and needs no paid account; managed environment charges, if any, are separate from that fact.

## Reproduce the verified container

Installed Docker is required. Use one container, no bind mounts, bounded resources, non-root user, tmpfs data, read-only root and a loopback-only published port. PostgreSQL trust authentication is permitted here only because it contains disposable synthetic records and is never publicly exposed. Real business PostgreSQL must use an approved least-privilege database identity.

```bash
docker pull postgres:17.9
docker run --detach --rm --name astro-p1-db-test --network bridge \
  --publish 127.0.0.1:55432:5432 --read-only --user postgres \
  --cap-drop ALL --security-opt no-new-privileges \
  --memory 512m --cpus 1 --pids-limit 128 \
  --tmpfs /var/lib/postgresql/data:rw,uid=999,gid=999,mode=0700 \
  --tmpfs /var/run/postgresql:rw,uid=999,gid=999,mode=0770 \
  --tmpfs /tmp:rw,mode=1777 \
  --env POSTGRES_DB=astro_test_p1 --env POSTGRES_HOST_AUTH_METHOD=trust \
  postgres@sha256:2a0d0fe14825b0939f78a8cad5cd4e6aa68bf94d0e5dd96e24b6d23af4315545
docker exec astro-p1-db-test pg_isready -U postgres -d astro_test_p1
```

Wait until ready, then run (the URL has no password and is **test-only**):

```bash
cd backend
TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/astro_test_p1 \
TEST_DATABASE_CONFIRM=astro_test_p1 ../.venv/bin/python -m pytest -q
cd ..
```

The four PostgreSQL tests execute migrations twice, downgrade/re-upgrade, verify hashed session storage/revocation/expiry, and bounded isolated activity through fresh database connections. A separate test harness verifies a real application process restart rather than merely constructing a new repository object.

## Application process, browser and backup/restore

Run `scripts/verify-p1-postgres.py` with installed backend dependencies and optional installed local Python Playwright/system Chromium. The app runtime does not require Playwright. In the Codex environment, Playwright is preinstalled globally and backend dependencies are in `.venv`; this exact wrapper was executed:

```bash
python - <<'PYCODE'
import runpy, subprocess, sys
site = subprocess.check_output(['.venv/bin/python', '-c', 'import sysconfig;print(sysconfig.get_paths()["purelib"])'], text=True).strip()
sys.path.insert(0, site)
runpy.run_path('scripts/verify-p1-postgres.py', run_name='__main__')
PYCODE
```

The script creates a private temporary TLS certificate/key, randomly generated in-memory synthetic app passwords and two test users. It starts credential-mode Uvicorn on HTTPS loopback 8443, verifies admin login, all twelve regression fixtures and their PostgreSQL history, stops/restarts the actual process, reuses the authenticated session/history, checks viewer restrictions and a real mobile browser, then runs `pg_dump --format=custom` and streams the archive into `pg_restore` for `astro_test_p1_restore`. It verifies schema readiness, the restored password hash, usable session token and twelve events. It revokes the original session and checks replay rejection.

The archive is private temporary data and is never printed or committed. The script tears down only the two named disposable test schemas/databases and its owned app process; temporary keys/passwords/archive disappear. A missing optional browser is explicitly BLOCKED, not a fake browser PASS. In this environment all **seven checks passed**, independently rerun by QA.

`scripts/verify-p1-db-outage.py` separately pauses only the owned synthetic DB container, verifies actual liveness/readiness/login failure and unpauses it in a cleanup block. Four actual outage/recovery checks passed independently; never run that harness against a shared/business database.

## Business backup procedure (not production-certified)

For an approved business database, separately configure least-privileged PostgreSQL tooling through protected environment/credential files without putting secrets in arguments. Run `pg_dump --format=custom --file=/approved/private/backup.dump` using the approved `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER` and protected credential mechanism. Encrypt/store the backup under the approved retention policy; these infrastructure choices are outside this build.

Restore into a distinct empty approved test database using `pg_restore --exit-on-error --no-owner --no-acl --dbname=approved_restore_database /approved/private/backup.dump`, never over the live database. Verify migration version, identity/hash/session handling and business records before accepting the recovery. The executed synthetic round-trip proves the local format/procedure; it does not establish a production RPO/RTO or an external backup service.

## Cleanup

```bash
docker stop astro-p1-db-test
```

`--rm` and tmpfs remove the disposable data. The downloaded public image can remain cached for later local QA. The initial attempted internal Docker network did not expose its loopback port; normal bridge worked. That bridge does not provide an OS egress firewall. No cloud DB, paid installation or remote credential was used.
