"""QA-MAF-001 regression: hardening applies to every response boundary."""
import pytest
from fastapi.testclient import TestClient
from app.main import create_app

@pytest.mark.parametrize('method,path,kwargs,status', [
 ('post','/api/auth/demo-login',{},403),
 ('post','/api/auth/demo-login',{'headers':{'Origin':'http://127.0.0.1:8000','Content-Length':'4097'}},413),
 ('post','/api/auth/demo-login',{'headers':{'Origin':'http://127.0.0.1:8000','Sec-Fetch-Site':'cross-site'}},403),
 ('get','/healthz',{'headers':{'Host':'attacker.invalid'}},400),
 ('get','/missing',{},404),
 ('get','/api/auth/me',{},401),
])
def test_headers_on_all_responses(method,path,kwargs,status):
 with TestClient(create_app(),base_url='http://127.0.0.1:8000') as client:
  response=getattr(client,method)(path,**kwargs)
 assert response.status_code==status
 assert response.headers['x-content-type-options']=='nosniff'
 assert response.headers['x-frame-options']=='DENY'
 assert response.headers['cache-control']=='no-store'
 assert "frame-ancestors 'none'" in response.headers['content-security-policy']
