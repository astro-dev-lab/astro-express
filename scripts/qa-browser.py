"""Independent P0 smoke: run installed Playwright with local system Chromium."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect

BASE = 'http://127.0.0.1:8000'
MATRIX = {
    'Stripe': ['Checkout success', 'Payment declined'],
    'HubSpot': ['Contact qualified', 'Duplicate'],
    'Notion': ['Create page', 'Permission denied'],
    'Resend': ['Email queued', 'Bounced'],
    'Twilio': ['Sms queued', 'Invalid number'],
    'Google': ['Calendar event created', 'Authorization rejected'],
}
ACTIONS = {
    'stripe': ['checkout-success', 'payment-declined'],
    'hubspot': ['contact-qualified', 'duplicate'],
    'notion': ['create-page', 'permission-denied'],
    'resend': ['email-queued', 'bounced'],
    'twilio': ['sms-queued', 'invalid-number'],
    'google': ['calendar-event-created', 'authorization-rejected'],
}
checks = []
def passed(label):
    checks.append(label)
    print('PASS:', label, flush=True)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
        args=['--no-sandbox', '--disable-crash-reporter', '--disable-crashpad', '--no-zygote'])
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    outgoing = []
    def guard(route):
        if urlsplit(route.request.url).netloc != '127.0.0.1:8000':
            outgoing.append(route.request.url)
            route.abort()
        else:
            route.continue_()
    context.route('**/*', guard)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    assert context.request.get(BASE + '/healthz').json() == {'status':'ok', 'mode':'simulation'}
    assert context.request.post(BASE+'/api/integrations/stripe/simulate', headers={'Origin':BASE},data={'action':'checkout-success'}).status == 401
    passed('health simulation and unauthenticated valid mutation rejected 401')
    page.goto(BASE)
    expect(page.get_by_role('button', name='Enter demo workspace')).to_be_visible()
    page.keyboard.press('Tab')
    assert page.evaluate('document.activeElement.tagName') == 'A'
    page.keyboard.press('Tab')
    expect(page.get_by_role('button', name='Enter demo workspace')).to_be_focused()
    page.keyboard.press('Enter')
    expect(page.get_by_text('SIMULATION — NO LIVE CONNECTIONS')).to_be_visible()
    expect(page.get_by_role('article')).to_have_count(6)
    expect(page.get_by_text('NOT CONNECTED', exact=True)).to_have_count(6)
    passed('keyboard login, six simulated disconnected cards')
    cookie = next(c for c in context.cookies() if c['name']=='astro_demo_session')
    assert cookie['httpOnly'] and cookie['sameSite']=='Strict'
    passed('actual browser HttpOnly and SameSite Strict session cookie')
    references = set()
    for provider, labels in MATRIX.items():
        for index, label in enumerate(labels):
            with page.expect_response(lambda r: f'/api/integrations/{provider.lower()}/simulate' in r.url) as info:
                page.get_by_role('button', name=f'{provider}: {label}', exact=True).click()
            response = info.value
            assert response.status == 200
            payload = response.json()
            assert payload['action'] == ACTIONS[provider.lower()][index]
            assert payload['status'] == ('success' if index == 0 else 'failed')
            assert payload['mode'] == 'simulated' and payload['connected'] is False
            assert payload['reference'].startswith('demo-') and payload['reference'] not in references
            references.add(payload['reference'])
            expect(page.locator('.result code')).to_have_text(payload['reference'])
            expect(page.locator('.activity li')).to_have_count(len(references))
            passed(f'{provider} {payload["action"]}: {payload["status"]}, unique reference + history')
    page.screenshot(path='docs/evidence/dashboard-desktop.png', full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    passed('desktop dashboard no horizontal overflow')
    isolated = browser.new_context()
    r=isolated.request.post(BASE+'/api/auth/demo-login',headers={'Origin':BASE},data={})
    assert r.status==200 and isolated.request.get(BASE+'/api/activity').json()=={'events':[]}
    isolated.close()
    passed('second browser session activity isolated')
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    expect(page.get_by_role('button',name='Google: Authorization rejected',exact=True)).to_be_enabled()
    page.screenshot(path='docs/evidence/dashboard-mobile.png',full_page=True)
    passed('390px mobile dashboard no horizontal overflow, controls enabled')
    page.get_by_role('button',name='Sign out',exact=True).click()
    expect(page.get_by_role('button',name='Enter demo workspace')).to_be_visible()
    assert context.request.get(BASE+'/api/auth/me').status==401
    context.add_cookies([cookie])
    assert context.request.get(BASE+'/api/auth/me').status==401
    passed('logout revoked server session and old-cookie replay rejected')
    page.get_by_role('button',name='Enter demo workspace').click()
    expect(page.locator('.activity li')).to_have_count(0)
    expect(page.get_by_text('Your first experiment starts here.')).to_be_visible()
    passed('fresh login has empty activity')
    failure_url = BASE + '/api/integrations/stripe/simulate'
    page.route(failure_url, lambda route: route.fulfill(status=403, body='Denied'))
    page.get_by_role('button',name='Stripe: Checkout success',exact=True).click()
    expect(page.get_by_role('alert')).to_contain_text('Request rejected')
    expect(page.get_by_role('button',name='Stripe: Checkout success',exact=True)).to_be_enabled()
    passed('403 security error displayed and controls reenabled')
    page.unroute(failure_url)
    page.route(failure_url, lambda route: route.abort())
    page.get_by_role('button',name='Stripe: Checkout success',exact=True).click()
    expect(page.get_by_role('alert')).to_contain_text('Unable to reach the local demo server')
    expect(page.get_by_role('button',name='Stripe: Checkout success',exact=True)).to_be_enabled()
    passed('local network failure displayed and controls reenabled')
    page.unroute(failure_url)
    pending = []
    page.route(failure_url, lambda route: pending.append(route))
    page.get_by_role('button',name='Stripe: Checkout success',exact=True).click()
    expect(page.get_by_role('button',name='Stripe: Checkout success',exact=True)).to_be_disabled()
    expect(page.get_by_role('button',name='Sign out',exact=True)).to_be_disabled()
    expect(page.get_by_role('button',name='Stripe: Checkout success',exact=True)).to_contain_text('Running')
    assert pending
    pending[0].continue_()
    expect(page.get_by_role('button',name='Stripe: Checkout success',exact=True)).to_be_enabled()
    page.unroute(failure_url)
    passed('pending simulation shows loading, disables controls, then recovers')
    for button in page.locator('button').all():
        box = button.bounding_box()
        assert box and box['height'] >= 44, box
    passed('mobile visible action/signout buttons have at least 44px height')
    assert not outgoing, outgoing
    assert not errors, errors
    passed('zero external browser requests and zero JavaScript errors')
    browser.close()
print(json.dumps({'passed':len(checks),'failed':0,'external_requests':outgoing,'javascript_errors':errors},indent=2))
