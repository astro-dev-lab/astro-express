"""Synthetic, disposable local PostgreSQL + TLS/process/backup proof.

Requires running approved container astro-p1-db-test; touches only astro_test_p1
and astro_test_p1_restore. No vendor credentials, sends, cloud or billing calls.
Run using Python with installed app dependencies and optional local Playwright.
"""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import httpx
from app.auth import hash_password
from app.migrate import migrate
from app.store import PostgresStore

DATABASE = 'postgresql://postgres@127.0.0.1:55432/astro_test_p1'
RESTORE = 'postgresql://postgres@127.0.0.1:55432/astro_test_p1_restore'
BASE = 'https://127.0.0.1:8443'
CONTAINER = 'astro-p1-db-test'
checks = []

def passed(label):
    checks.append(label)
    print('PASS:', label, flush=True)

def docker(*args, **kwargs):
    return subprocess.run(['docker', 'exec', '-i', CONTAINER, *args], check=True, capture_output=True, **kwargs)

with tempfile.TemporaryDirectory(prefix='astro-p1-proof-') as directory:
    directory = Path(directory)
    cert, key = directory / 'certificate.pem', directory / 'private-key.pem'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),'-days','1','-subj','/CN=localhost','-addext','subjectAltName=IP:127.0.0.1,DNS:localhost'],check=True,capture_output=True)
    key.chmod(0o600)
    migrate(DATABASE, 'up')
    store = PostgresStore(DATABASE)
    admin_password, viewer_password = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    admin = store.create_user('proof_admin', 'Synthetic Administrator', 'admin', hash_password(admin_password))
    store.create_user('proof_viewer', 'Synthetic Viewer', 'viewer', hash_password(viewer_password))
    env = dict(os.environ, APP_MODE='production', APP_ORIGIN=BASE,
               PRODUCTION_ACK='I_ACCEPT_PRODUCTION_SECURITY_REQUIREMENTS', DATABASE_URL=DATABASE)
    for name in ['PGHOSTADDR','PGSERVICE','PGSERVICEFILE','PGOPTIONS']:
        env.pop(name, None)
    python = str(ROOT / '.venv/bin/python')
    server = None
    def stop_server(process):
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    def start_server():
        process = subprocess.Popen([python,'-m','uvicorn','app.main:app','--app-dir',str(ROOT/'backend'),'--host','127.0.0.1','--port','8443','--workers','1','--no-access-log','--no-proxy-headers','--timeout-graceful-shutdown','2','--ssl-certfile',str(cert),'--ssl-keyfile',str(key)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            if process.poll() is not None:
                raise AssertionError('Synthetic production server failed startup')
            try:
                if httpx.get(BASE+'/readyz',verify=str(cert),timeout=1).status_code == 200:
                    return process
            except httpx.TransportError:
                pass
            time.sleep(.1)
        stop_server(process)
        raise AssertionError('Synthetic production startup timeout')
    try:
        server = start_server()
        with httpx.Client(base_url=BASE,verify=str(cert),headers={'Origin':BASE}) as client:
            assert client.post('/api/auth/demo-login').status_code == 404
            assert client.post('/api/auth/login',json={'username':'proof_admin','password':secrets.token_urlsafe(32)}).status_code == 401
            r=client.post('/api/auth/login',json={'username':'proof_admin','password':admin_password})
            assert r.status_code == 200 and r.json()['user']['role']=='admin'
            csrf = r.json()['csrf_token']
            passed('real PostgreSQL HTTPS credential login; demo auto-login disabled')
            fixtures = {'stripe':['checkout-success','payment-declined'],'hubspot':['contact-qualified','duplicate'],'notion':['create-page','permission-denied'],'resend':['email-queued','bounced'],'twilio':['sms-queued','invalid-number'],'google':['calendar-event-created','authorization-rejected']}
            for provider, actions in fixtures.items():
                for index, action in enumerate(actions):
                    r=client.post(f'/api/integrations/{provider}/simulate',headers={'X-CSRF-Token':csrf},json={'action':action})
                    assert r.status_code==200
                    assert r.json()['mode']=='simulated' and r.json()['connected'] is False
                    assert r.json()['status']==('success' if index==0 else 'failed')
            assert len(client.get('/api/activity').json()['events']) == 12
            passed('all 12 regression fixtures authenticated and recorded in real PostgreSQL')
            stop_server(server)
            server=start_server()
            assert client.get('/api/auth/me').json()['user']['role']=='admin'
            assert len(client.get('/api/activity').json()['events']) == 12
            passed('actual uvicorn process restart preserves authenticated session and activity')
            with httpx.Client(base_url=BASE,verify=str(cert),headers={'Origin':BASE}) as viewer:
                r=viewer.post('/api/auth/login',json={'username':'proof_viewer','password':viewer_password})
                assert r.status_code==200
                assert viewer.get('/api/activity').json()=={'events':[]}
                assert viewer.post('/api/integrations/stripe/simulate',headers={'X-CSRF-Token':r.json()['csrf_token']},json={'action':'checkout-success'}).status_code==403
                assert viewer.post('/api/auth/logout',headers={'X-CSRF-Token':r.json()['csrf_token']}).status_code==200
            passed('real PostgreSQL viewer read-only/isolation/logout')
            try:
                from playwright.sync_api import sync_playwright, expect
            except ImportError:
                print('BLOCKED: optional local browser tooling unavailable',flush=True)
            else:
                with sync_playwright() as p:
                    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-crashpad','--no-zygote','--single-process'])
                    context=browser.new_context(ignore_https_errors=True,viewport={'width':390,'height':844})
                    outgoing=[];errors=[]
                    def guard(route):
                        if urlsplit(route.request.url).netloc!='127.0.0.1:8443':
                            outgoing.append(route.request.url);route.abort()
                        else: route.continue_()
                    context.route('**/*',guard)
                    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(BASE)
                    expect(page.get_by_role('button',name='Enter demo workspace')).to_have_count(0)
                    page.get_by_label('Username',exact=True).fill('proof_admin')
                    page.get_by_label('Password',exact=True).fill(admin_password)
                    page.get_by_role('button',name='Sign in',exact=True).click()
                    expect(page.get_by_role('article')).to_have_count(6)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    page.get_by_role('button',name='Sign out',exact=True).click()
                    expect(page.get_by_role('button',name='Sign in',exact=True)).to_be_visible()
                    page.get_by_label('Username',exact=True).fill('proof_viewer')
                    page.get_by_label('Password',exact=True).fill(viewer_password)
                    page.get_by_role('button',name='Sign in',exact=True).click()
                    expect(page.get_by_role('article')).to_have_count(6)
                    buttons=page.locator('.actions button')
                    assert buttons.count()==12 and all(buttons.nth(i).is_disabled() for i in range(12))
                    assert not outgoing and not errors
                    browser.close()
                passed('actual mobile credential browser admin/viewer flow; zero external requests/errors')
            with store.connection() as conn:
                session_count=conn.execute('SELECT count(*) AS n FROM app_sessions').fetchone()['n']
            archive=docker('pg_dump','-U','postgres','-d','astro_test_p1','--format=custom').stdout
            backup=directory/'synthetic.dump';backup.write_bytes(archive);backup.chmod(0o600)
            docker('createdb','-U','postgres','astro_test_p1_restore')
            docker('pg_restore','-U','postgres','-d','astro_test_p1_restore','--exit-on-error','--no-owner','--no-acl',input=archive)
            restored=PostgresStore(RESTORE);assert restored.ready()
            assert len(restored.activity(admin))==12
            assert str(restored.session_user(client.cookies.get('astro_demo_session'))['id']) == admin
            with restored.connection() as conn:
                row=conn.execute('SELECT count(*) AS n FROM app_sessions').fetchone()
                assert row['n']==session_count
                user=conn.execute('SELECT password_hash FROM app_users WHERE username=%s',('proof_admin',)).fetchone()
                from app.auth import verify_password
                assert verify_password(user['password_hash'],admin_password)
            passed('pg_dump/pg_restore synthetic round-trip verifies schema, password hash, sessions and 12 events')
            replay=client.cookies.get('astro_demo_session')
            assert client.post('/api/auth/logout',headers={'X-CSRF-Token':csrf}).status_code==200
            client.cookies.set('astro_demo_session',replay)
            assert client.get('/api/auth/me').status_code==401
            passed('real PostgreSQL logout revokes old-cookie replay')
    finally:
        if server is not None and server.poll() is None:
            stop_server(server)
        docker('dropdb','-U','postgres','--if-exists','astro_test_p1_restore')
        migrate(DATABASE,'down','astro_test_p1')
print(json.dumps({'passed':len(checks),'failed':0,'actual_postgresql':True,'provider_tests':'regression fixtures only'}))
