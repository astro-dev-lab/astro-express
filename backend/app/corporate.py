"""G2 solo-owner workflow. Additive PostgreSQL schema; no outbound connector.

Only the designated authenticated human owner can mutate or approve. A service
principal is not a user and cannot approve. Contract jobs are always BLOCKED.
"""
import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import uuid
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from .store import PostgresStore

REPOSITORY_ID = 1109489408
REPOSITORY_NAME = "astro-dev-lab/me-fastapi"
ACTION = "APPROVE_ZERO_COST_CONTRACT"
BLOCKED = "BLOCKED_UPSTREAM_AUTHORIZATION"
KEY = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# Defense in depth; arbitrary free text is not a secrets store.
SENSITIVE = re.compile(r"https?://[^\s]*@|authorization\s*:|bearer\s+|(?:password|secret|token|api[_ -]?key)\s*[:=]|(?:gh[pousr]_|github_pat_|sk_live_|sk_test_|AKIA)[A-Za-z0-9_]+|-----BEGIN", re.I)

class GuardError(Exception):
    """Constant safe text only; do not include submitted inputs."""

@dataclass(frozen=True)
class Actor:
    id: str
    kind: str

    def require_owner(self, owner_id):
        if self.kind != "human" or str(self.id) != str(owner_id):
            raise GuardError("Designated human owner required")


def repository_contract():
    return {"id": REPOSITORY_ID, "name": REPOSITORY_NAME}


def safe_text(value, limit):
    if not isinstance(value,str) or not value.strip() or len(value) > limit or SENSITIVE.search(value) or any(ord(c)<32 and c not in '\n\t' for c in value):
        raise GuardError("Invalid text; never include credentials")
    return value.strip()


def validate_intake(data):
    if set(data) != {"title", "objective", "acceptance"}:
        raise GuardError("Invalid intake fields")
    return {k:safe_text(data[k],n) for k,n in [("title",120),("objective",1000),("acceptance",1000)]}


def identifier(value):
    try: return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError): raise GuardError("Invalid identifier") from None


def key(value):
    if not isinstance(value,str) or not KEY.fullmatch(value): raise GuardError("Invalid idempotency reference")
    return value


class PilotAdapter:
    """In-memory contract fixture only. No token, SDK, HTTP, labels or factory run."""
    dispatch_status = BLOCKED

    def __init__(self): self.issues = {}

    def ensure_issue(self, repository, work_id, payload):
        if repository != repository_contract(): raise GuardError("Repository is not allowlisted")
        marker = f"{REPOSITORY_ID}:{work_id}"
        self.issues.setdefault(marker,"contract-"+hashlib.sha256(marker.encode()).hexdigest()[:24])
        return self.issues[marker]

    def live_dispatch(self, issue_reference):
        raise GuardError("Live dispatch blocked: upstream trigger authorization not enforceable")


def migrate_corporate(base, direction="up", confirm=None):
    name=urlsplit(base.database_url).path.lstrip('/')
    if direction not in {"up","down"} or (direction=="down" and (not name.startswith('astro_test_') or confirm!=name)):
        raise GuardError("Downgrade requires exact disposable database confirmation")
    with base.connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s)",(726081342,))
        conn.execute("CREATE TABLE IF NOT EXISTS corporate_schema_migrations(version integer PRIMARY KEY)")
        versions=[r['version'] for r in conn.execute("SELECT version FROM corporate_schema_migrations").fetchall()]
        if any(v!=1 for v in versions): raise GuardError("Unknown Corporate migration version")
        if direction=='up' and not versions:
            # Requires P1 to be migrated first; FK failures roll back atomically.
            conn.execute(Path(__file__).with_name('corporate.up.sql').read_text())
            conn.execute("INSERT INTO corporate_schema_migrations VALUES (1)")
        elif direction=='down' and versions:
            conn.execute(Path(__file__).with_name('corporate.down.sql').read_text())
            conn.execute("DELETE FROM corporate_schema_migrations WHERE version=1")


class CorporateStore:
    def __init__(self,base): self.base=base

    def ready(self,conn):
        if [row['version'] for row in conn.execute("SELECT version FROM corporate_schema_migrations ORDER BY version").fetchall()] != [1]:
            raise GuardError("Corporate migrations required")

    def owner(self,conn,actor):
        self.ready(conn)
        row=conn.execute("SELECT u.id,u.blocked,u.role FROM corporate_owner o JOIN app_users u ON u.id=o.user_id FOR SHARE OF u").fetchone()
        if not row or row['blocked'] or row['role']!='admin': raise GuardError("Active owner not provisioned")
        actor.require_owner(row['id'])

    @staticmethod
    def audit(conn,actor,event,record_id=None,cents=None):
        conn.execute("INSERT INTO corporate_audit(actor_id,event,record_id,cents) VALUES (%s,%s,%s,%s)",(identifier(actor.id),event,record_id,cents))

    def provision_owner(self,username):
        with self.base.connection() as conn:
            self.ready(conn)
            conn.execute("SELECT pg_advisory_xact_lock(%s)",(726081343,))
            user=conn.execute("SELECT id,role,blocked FROM app_users WHERE username=%s FOR UPDATE",(username,)).fetchone()
            if not user or user['role']!='admin' or user['blocked']: raise GuardError("Provision an active administrator first")
            if conn.execute("SELECT user_id FROM corporate_owner").fetchone(): raise GuardError("Owner already provisioned; no reassignment API")
            conn.execute("INSERT INTO corporate_owner(user_id) VALUES (%s)",(user['id'],))
            self.audit(conn,Actor(str(user['id']),'human'),'owner_provisioned')

    def create_project(self,actor,name):
        name=safe_text(name,80)
        with self.base.connection() as conn:
            self.owner(conn,actor)
            result=conn.execute("INSERT INTO corporate_projects(id,name,repository_id,repository_name) VALUES (%s,%s,%s,%s) RETURNING *",(str(uuid.uuid4()),name,REPOSITORY_ID,REPOSITORY_NAME)).fetchone()
            self.audit(conn,actor,'project_created',result['id'])
            return result

    def intake(self,actor,project_id,request_key,payload):
        payload=validate_intake(payload); project_id=identifier(project_id); request_key=key(request_key)
        digest=hashlib.sha256(json.dumps({'project_id':project_id,**payload},sort_keys=True,separators=(',',':')).encode()).hexdigest()
        with self.base.connection() as conn:
            self.owner(conn,actor)
            if not conn.execute("SELECT id FROM corporate_projects WHERE id=%s AND repository_id=%s AND repository_name=%s",(project_id,REPOSITORY_ID,REPOSITORY_NAME)).fetchone(): raise GuardError("Allowlisted project required")
            row=conn.execute("INSERT INTO corporate_work(id,project_id,request_key,title,objective,acceptance,digest,submitted_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(request_key) DO NOTHING RETURNING *",(str(uuid.uuid4()),project_id,request_key,payload['title'],payload['objective'],payload['acceptance'],digest,identifier(actor.id))).fetchone()
            if row:
                self.audit(conn,actor,'work_submitted',row['id']); return row
            row=conn.execute("SELECT * FROM corporate_work WHERE request_key=%s",(request_key,)).fetchone()
            if row['digest']!=digest: raise GuardError("Idempotency reference conflicts with submitted work")
            return row

    def approve(self,actor,work_id,digest,confirmation):
        work_id=identifier(work_id)
        if confirmation!=ACTION: raise GuardError("Deliberate zero-cost contract approval required")
        with self.base.connection() as conn:
            self.owner(conn,actor)
            work=conn.execute("SELECT * FROM corporate_work WHERE id=%s FOR UPDATE",(work_id,)).fetchone()
            if not work or work['digest']!=digest: raise GuardError("Approval must match immutable work digest")
            existing=conn.execute("SELECT * FROM corporate_approvals WHERE work_id=%s",(work_id,)).fetchone()
            if existing: return existing
            row=conn.execute("INSERT INTO corporate_approvals(id,work_id,owner_id,digest,max_cents,action,expires_at) VALUES (%s,%s,%s,%s,0,%s,%s) RETURNING *",(str(uuid.uuid4()),work_id,identifier(actor.id),digest,ACTION,datetime.now(timezone.utc)+timedelta(days=1))).fetchone()
            self.audit(conn,actor,'work_approved',row['id'],0)
            return row

    def dispatch(self,actor,work_id,reserve_cents=0,now=None):
        if type(reserve_cents)!=int or reserve_cents!=0: raise GuardError("G2 incremental budget is zero")
        work_id=identifier(work_id)
        with self.base.connection() as conn:
            self.owner(conn,actor)
            conn.execute("SELECT singleton FROM corporate_budget WHERE singleton=true FOR UPDATE")
            work=conn.execute("SELECT * FROM corporate_work WHERE id=%s FOR UPDATE",(work_id,)).fetchone()
            approval=conn.execute("SELECT * FROM corporate_approvals WHERE work_id=%s",(work_id,)).fetchone()
            if not work or not approval or approval['digest']!=work['digest'] or approval['max_cents']!=0 or approval['expires_at']<=(now or datetime.now(timezone.utc)):
                raise GuardError("Current matching CEO approval required")
            existing=conn.execute("SELECT * FROM corporate_jobs WHERE work_id=%s",(work_id,)).fetchone()
            if existing: return existing
            # Contract adapter only: NEVER replace with a live label call.
            issue=PilotAdapter().ensure_issue(repository_contract(),work_id,work)
            row=conn.execute("INSERT INTO corporate_jobs(id,work_id,approval_id,mode,status,issue_reference) VALUES (%s,%s,%s,'contract',%s,%s) RETURNING *",(str(uuid.uuid4()),work_id,approval['id'],BLOCKED,issue)).fetchone()
            conn.execute("INSERT INTO corporate_reservations(job_id,cents) VALUES (%s,0)",(row['id'],))
            self.audit(conn,actor,'contract_reserved',row['id'],0)
            self.audit(conn,actor,'live_dispatch_blocked',row['id'],0)
            return row

    def record_actual(self,actor,job_id,cents,reference):
        if type(cents)!=int or cents!=0: raise GuardError("G2 incremental budget is zero")
        job_id=identifier(job_id); reference=key(reference)
        with self.base.connection() as conn:
            self.owner(conn,actor)
            conn.execute("SELECT singleton FROM corporate_budget WHERE singleton=true FOR UPDATE")
            if not conn.execute("SELECT job_id FROM corporate_reservations WHERE job_id=%s FOR UPDATE",(job_id,)).fetchone(): raise GuardError("Existing reservation required")
            existing=conn.execute("SELECT * FROM corporate_actuals WHERE job_id=%s OR reference=%s",(job_id,reference)).fetchone()
            if existing:
                if str(existing['job_id'])!=job_id or existing['reference']!=reference: raise GuardError("Actual-cost reference conflict")
                return existing
            row=conn.execute("INSERT INTO corporate_actuals(job_id,reference,cents) VALUES (%s,%s,0) RETURNING *",(job_id,reference)).fetchone()
            self.audit(conn,actor,'actual_recorded',job_id,0)
            return row

    def snapshot(self,actor):
        with self.base.connection() as conn:
            self.owner(conn,actor)
            # Bounded responses; database records remain durable, not silently deleted.
            result={name:conn.execute(f"SELECT * FROM {table} ORDER BY created_at DESC LIMIT 100").fetchall() for name,table in [('projects','corporate_projects'),('work','corporate_work'),('approvals','corporate_approvals'),('jobs','corporate_jobs')]}
            result['audit']=conn.execute("SELECT * FROM corporate_audit ORDER BY id DESC LIMIT 100").fetchall()
            result['costs']={'currency':'USD','limit_cents':0,'reserved_cents':conn.execute("SELECT coalesce(sum(cents),0) AS cents FROM corporate_reservations").fetchone()['cents'],'actual_cents':conn.execute("SELECT coalesce(sum(cents),0) AS cents FROM corporate_actuals").fetchone()['cents'],'actuals':conn.execute("SELECT * FROM corporate_actuals ORDER BY created_at DESC LIMIT 100").fetchall()}
            result['connections']={'repository':repository_contract(),'mode':'contract','live_dispatch':BLOCKED,'principals':conn.execute("SELECT * FROM corporate_principals").fetchall()}
            return result


class StrictBody(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
class ProjectBody(StrictBody):
    name: str=Field(min_length=1,max_length=80)
class WorkBody(StrictBody):
    project_id: str
    request_key: str=Field(min_length=1,max_length=64)
    title: str=Field(min_length=1,max_length=120)
    objective: str=Field(min_length=1,max_length=1000)
    acceptance: str=Field(min_length=1,max_length=1000)
class ApprovalBody(StrictBody):
    digest: str=Field(pattern=r'^[0-9a-f]{64}$')
    confirmation: str
class DispatchBody(StrictBody):
    reserve_cents: int=0
class ActualBody(StrictBody):
    cents: int
    reference: str=Field(min_length=1,max_length=64)


def attach_corporate(app,base,authorized,database_call):
    router=APIRouter(prefix='/api/corporate')
    async def invoke(request,mutate,method,*args):
        if base is None: raise HTTPException(404,'Corporate requires provisioned credential authentication')
        session=await authorized(request,mutate)
        store=CorporateStore(base)
        try: return await database_call(getattr(store,method),Actor(session['user']['id'],'human'),*args)
        except GuardError as e: raise HTTPException(409,str(e)) from None
    @router.get('/snapshot')
    async def snapshot(request:Request): return await invoke(request,False,'snapshot')
    @router.post('/projects')
    async def project(body:ProjectBody,request:Request): return await invoke(request,True,'create_project',body.name)
    @router.post('/work')
    async def work(body:WorkBody,request:Request): return await invoke(request,True,'intake',body.project_id,body.request_key,body.model_dump(include={'title','objective','acceptance'}))
    @router.post('/work/{work_id}/approve')
    async def approval(work_id:str,body:ApprovalBody,request:Request): return await invoke(request,True,'approve',work_id,body.digest,body.confirmation)
    @router.post('/work/{work_id}/dispatch-contract')
    async def dispatch(work_id:str,body:DispatchBody,request:Request): return await invoke(request,True,'dispatch',work_id,body.reserve_cents)
    @router.post('/jobs/{job_id}/actual')
    async def actual(job_id:str,body:ActualBody,request:Request): return await invoke(request,True,'record_actual',job_id,body.cents,body.reference)
    app.include_router(router)


def main():
    parser=argparse.ArgumentParser(description='G2 additive local Corporate setup; no outbound connector')
    parser.add_argument('action',choices=['up','down','provision-owner'])
    parser.add_argument('--username')
    parser.add_argument('--confirm-disposable-database')
    args=parser.parse_args()
    try:
        base=PostgresStore(os.environ.get('DATABASE_URL',''))
        if args.action=='provision-owner':
            if not os.isatty(0): raise GuardError('Owner provisioning requires local interactive operator')
            CorporateStore(base).provision_owner(args.username)
        else: migrate_corporate(base,args.action,args.confirm_disposable_database)
    except Exception:
        parser.exit(1,'Corporate setup blocked; check local schema, active administrator and explicit configuration.\n')
    print('Corporate setup completed')

if __name__=='__main__': main()
