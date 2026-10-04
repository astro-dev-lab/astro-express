"""Controlled outage of our disposable synthetic PostgreSQL container only."""
from pathlib import Path
import secrets
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from fastapi.testclient import TestClient
from app.config import Settings, ACK
from app.main import create_app
from app.migrate import migrate

URL='postgresql://postgres@127.0.0.1:55432/astro_test_p1'
ORIGIN='https://127.0.0.1:8443'
CONTAINER='astro-p1-db-test'
settings=Settings(mode='production',origin=ORIGIN,production_ack=ACK,database_url=URL)
migrate(URL,'up')
paused=False
try:
    with TestClient(create_app(settings),base_url=ORIGIN) as client:
        assert client.get('/readyz').status_code==200
        subprocess.run(['docker','pause',CONTAINER],check=True,capture_output=True)
        paused=True
        assert client.get('/healthz').status_code==200
        print('PASS: actual paused PostgreSQL leaves liveness 200',flush=True)
        response=client.get('/readyz')
        assert response.status_code==503 and 'temporarily unavailable' in response.text
        assert response.headers['x-content-type-options']=='nosniff'
        print('PASS: actual database outage yields generic hardened readiness 503',flush=True)
        password=secrets.token_urlsafe(32)
        response=client.post('/api/auth/login',headers={'Origin':ORIGIN},json={'username':'outage_probe','password':password})
        assert response.status_code==503 and password not in response.text
        print('PASS: actual database outage blocks credential login without password echo',flush=True)
        subprocess.run(['docker','unpause',CONTAINER],check=True,capture_output=True)
        paused=False
        assert client.get('/readyz').status_code==200
        print('PASS: real PostgreSQL readiness recovers after unpause',flush=True)
finally:
    if paused:
        subprocess.run(['docker','unpause',CONTAINER],check=True,capture_output=True)
    migrate(URL,'down','astro_test_p1')
print('Actual database outage: 4 passed, 0 failed')
