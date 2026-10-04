"""Actual synthetic G2 TLS/PostgreSQL/browser/process restart proof.

Only astro-g2-db-test/astro_test_g2, loopback ports55433/8444. No live adapters,
cloud, provider accounts or paid calls. Random passwords remain in memory.
"""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
import httpx
from app.auth import hash_password
from app.migrate import migrate
from app.store import PostgresStore
from app.corporate import migrate_corporate, CorporateStore
DB='postgresql://postgres@127.0.0.1:55433/astro_test_g2'
BASE='https://127.0.0.1:8444'
checks=[]
def passed(label): checks.append(label); print('PASS:',label,flush=True)
def stop(process):
    process.terminate()
    try: process.wait(timeout=10)
    except subprocess.TimeoutExpired: process.kill();process.wait(timeout=5)
with tempfile.TemporaryDirectory(prefix='astro-g2-proof-') as temporary:
    directory=Path(temporary);cert=directory/'certificate.pem';key=directory/'private-key.pem'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),'-days','1','-subj','/CN=localhost','-addext','subjectAltName=IP:127.0.0.1,DNS:localhost'],check=True,capture_output=True)
    key.chmod(0o600)
    migrate(DB);base=PostgresStore(DB);migrate_corporate(base)
    password=secrets.token_urlsafe(32)
    base.create_user('g2_proof_owner','Synthetic Owner','admin',hash_password(password))
    CorporateStore(base).provision_owner('g2_proof_owner')
    env=dict(os.environ,APP_MODE='production',APP_ORIGIN=BASE,PRODUCTION_ACK='I_ACCEPT_PRODUCTION_SECURITY_REQUIREMENTS',DATABASE_URL=DB)
    for name in ['PGHOSTADDR','PGSERVICE','PGSERVICEFILE','PGOPTIONS']: env.pop(name,None)
    process=None
    def start():
        child=subprocess.Popen([str(ROOT/'.venv/bin/python'),'-m','uvicorn','app.main:app','--app-dir',str(ROOT/'backend'),'--host','127.0.0.1','--port','8444','--no-access-log','--no-proxy-headers','--timeout-graceful-shutdown','2','--ssl-certfile',str(cert),'--ssl-keyfile',str(key)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            if child.poll() is not None: raise AssertionError('Synthetic G2 server failed startup')
            try:
                if httpx.get(BASE+'/readyz',verify=str(cert),timeout=1).status_code==200:return child
            except httpx.TransportError:pass
            time.sleep(.1)
        stop(child);raise AssertionError('Synthetic G2 startup timeout')
    try:
        process=start()
        with httpx.Client(base_url=BASE,verify=str(cert),timeout=10) as client:
            assert client.get('/api/corporate/snapshot').status_code==401
            assert client.post('/api/auth/demo-login',headers={'Origin':BASE},json={}).status_code==404
            login=client.post('/api/auth/login',headers={'Origin':BASE},json={'username':'g2_proof_owner','password':password})
            assert login.status_code==200
            headers={'Origin':BASE,'X-CSRF-Token':login.json()['csrf_token']}
            passed('Real TLS credential login; anonymous Corporate denied; demo auto-login unavailable')
            cards=client.get('/api/integrations').json()['integrations']
            for card in cards:
                for action in card['actions']:
                    r=client.post(f"/api/integrations/{card['id']}/simulate",headers=headers,json={'action':action['id']})
                    assert r.status_code==200 and r.json()['mode']=='simulated' and r.json()['connected'] is False
            assert len(client.get('/api/activity').json()['events'])==12
            passed('All twelve P1 synthetic scenarios preserved; no live vendor claim')
            from playwright.sync_api import sync_playwright
            errors=[];external=[]
            with sync_playwright() as playwright:
                browser=playwright.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
                context=browser.new_context(ignore_https_errors=True,viewport={'width':390,'height':844})
                def route(handler):
                    if urlsplit(handler.request.url).hostname!='127.0.0.1': external.append(handler.request.url);handler.abort()
                    else:handler.continue_()
                context.route('**/*',route)
                page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(BASE+'/corporate')
                page.get_by_label('Username',exact=True).fill('g2_proof_owner')
                page.get_by_label('Password',exact=True).fill(password)
                page.get_by_label('Password',exact=True).press('Enter')
                page.get_by_role('button',name='Projects',exact=True).wait_for()
                assert page.get_by_role('navigation').get_by_role('button').count()==6
                page.get_by_label('Project name').fill('Synthetic Browser Project')
                page.get_by_role('button',name='Add project',exact=True).click()
                page.get_by_text('Project recorded.',exact=True).wait_for()
                page.get_by_role('button',name='New Work',exact=True).click()
                page.get_by_label('Title',exact=True).fill('Synthetic browser task')
                page.get_by_label('Objective',exact=True).fill('Improve local quality')
                page.get_by_label('Acceptance criteria',exact=True).fill('All local tests pass')
                page.get_by_role('button',name='Submit intake',exact=True).click()
                page.get_by_text('Intake saved. Review and approve it separately.',exact=True).wait_for()
                before=client.get('/api/corporate/snapshot').json()
                assert len(before['work'])==1 and before['approvals']==before['jobs']==[]
                page.get_by_role('button',name='Review/Approve',exact=True).click()
                approval=page.get_by_role('button',name='Approve zero-cost contract',exact=True)
                assert approval.is_disabled()
                page.get_by_role('checkbox').check();approval.click()
                page.get_by_text('Distinct owner approval recorded.',exact=True).wait_for()
                page.get_by_role('button',name='Jobs',exact=True).click()
                page.get_by_role('button',name='Prepare zero-cost contract',exact=True).click()
                page.get_by_text('Contract reservation recorded; live dispatch remains blocked.',exact=True).wait_for()
                page.get_by_role('button',name='Costs',exact=True).click()
                page.get_by_role('button',name='Record $0 contract actual',exact=False).click()
                page.get_by_text('Zero-cost contract actual recorded.',exact=True).wait_for()
                page.get_by_role('button',name='Connections',exact=True).click()
                assert 'BLOCKED_UPSTREAM_AUTHORIZATION' in page.locator('main').inner_text()
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                for button in page.get_by_role('button').all(): assert button.bounding_box()['height']>=44
                page.get_by_role('button',name='Projects',exact=True).focus()
                page.keyboard.press('Tab')
                assert page.evaluate('document.activeElement.tagName')=='BUTTON'
                page.keyboard.press('Enter')
                page.get_by_label('Title',exact=True).wait_for()
                assert not errors and not external
                passed('Six-section mobile browser: intake, separate deliberate approval, blocked contract, zero actual; keyboard and 44px controls')
                page.get_by_role('button',name='Sign out',exact=True).click()
                page.get_by_role('button',name='Sign in',exact=True).wait_for()
                assert 'Password' in page.locator('main').inner_text()
                browser.close()
            before=client.get('/api/corporate/snapshot').json()
            assert len(before['jobs'])==len(before['approvals'])==len(before['costs']['actuals'])==1
            assert before['costs']['limit_cents']==before['costs']['actual_cents']==0
            stop(process);process=None;process=start()
            after=client.get('/api/corporate/snapshot').json()
            assert before==after
            passed('Actual app process restart preserves authenticated session, projects, intake, approvals, jobs, budget and audit')
            work=after['work'][0];job=after['jobs'][0]
            replay=client.post(f"/api/corporate/work/{work['id']}/dispatch-contract",headers=headers,json={})
            assert replay.status_code==200 and replay.json()['id']==job['id']
            assert len(client.get('/api/corporate/snapshot').json()['jobs'])==1
            for cents in [-1,1,20000]:
                assert client.post(f"/api/corporate/jobs/{job['id']}/actual",headers=headers,json={'cents':cents,'reference':'denied'}).status_code==409
            passed('Idempotent retry creates no duplicate job/issue marker; every nonzero actual blocked')
            assert client.post('/api/auth/logout',headers=headers,json={}).status_code==200
            assert client.get('/api/corporate/snapshot').status_code==401
            passed('Logout revokes Corporate access; browser recorded zero outside-origin requests and zero JavaScript errors')
    finally:
        if process is not None: stop(process)
        migrate_corporate(base,'down','astro_test_g2')
        migrate(DB,'down','astro_test_g2')
print(f'{len(checks)} actual G2 runtime checks passed; 0 failed')
