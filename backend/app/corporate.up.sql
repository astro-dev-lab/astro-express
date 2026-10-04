-- G2 additive schema. Never changes the P1 schema version or P1 tables.
CREATE TABLE corporate_owner (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    user_id uuid UNIQUE NOT NULL REFERENCES app_users(id)
);
CREATE TABLE corporate_principals (
    id varchar(48) PRIMARY KEY,
    kind varchar(16) NOT NULL CHECK(kind='service'),
    capability varchar(32) NOT NULL CHECK(capability='contract_only')
);
INSERT INTO corporate_principals VALUES ('foreman-contract','service','contract_only');
CREATE TABLE corporate_projects (
    id uuid PRIMARY KEY,
    name varchar(80) NOT NULL CHECK(length(trim(name)) > 0),
    repository_id bigint NOT NULL CHECK(repository_id=1109489408),
    repository_name text NOT NULL CHECK(repository_name='astro-dev-lab/me-fastapi'),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE corporate_work (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES corporate_projects(id),
    request_key varchar(64) UNIQUE NOT NULL,
    title varchar(120) NOT NULL,
    objective varchar(1000) NOT NULL,
    acceptance varchar(1000) NOT NULL,
    digest char(64) NOT NULL,
    submitted_by uuid NOT NULL REFERENCES app_users(id),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE corporate_approvals (
    id uuid PRIMARY KEY,
    work_id uuid UNIQUE NOT NULL REFERENCES corporate_work(id),
    owner_id uuid NOT NULL REFERENCES app_users(id),
    digest char(64) NOT NULL,
    max_cents integer NOT NULL CHECK(max_cents=0),
    action varchar(40) NOT NULL CHECK(action='APPROVE_ZERO_COST_CONTRACT'),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);
CREATE TABLE corporate_budget (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    limit_cents integer NOT NULL CHECK(limit_cents=0)
);
INSERT INTO corporate_budget VALUES (true,0);
CREATE TABLE corporate_jobs (
    id uuid PRIMARY KEY,
    work_id uuid UNIQUE NOT NULL REFERENCES corporate_work(id),
    approval_id uuid UNIQUE NOT NULL REFERENCES corporate_approvals(id),
    mode varchar(16) NOT NULL CHECK(mode='contract'),
    status varchar(40) NOT NULL CHECK(status='BLOCKED_UPSTREAM_AUTHORIZATION'),
    issue_reference varchar(80) UNIQUE NOT NULL CHECK(issue_reference LIKE 'contract-%'),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE corporate_reservations (
    job_id uuid PRIMARY KEY REFERENCES corporate_jobs(id),
    cents integer NOT NULL CHECK(cents=0),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE corporate_actuals (
    job_id uuid PRIMARY KEY REFERENCES corporate_jobs(id),
    reference varchar(64) UNIQUE NOT NULL,
    cents integer NOT NULL CHECK(cents=0),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE corporate_audit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id uuid NOT NULL REFERENCES app_users(id),
    event varchar(40) NOT NULL,
    record_id uuid,
    cents integer CHECK(cents=0),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE FUNCTION corporate_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Corporate records are append-only'; END; $$;
DO $$ DECLARE t text; BEGIN
    FOREACH t IN ARRAY ARRAY['owner','principals','projects','work','approvals','budget','jobs','reservations','actuals','audit'] LOOP
        EXECUTE format('CREATE TRIGGER corporate_no_change BEFORE UPDATE OR DELETE OR TRUNCATE ON corporate_%I FOR EACH STATEMENT EXECUTE FUNCTION corporate_immutable()',t);
    END LOOP;
END; $$;
