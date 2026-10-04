CREATE TABLE app_users (
    id uuid PRIMARY KEY,
    username varchar(64) UNIQUE NOT NULL CHECK (username ~ '^[a-z0-9][a-z0-9_.-]{2,63}$'),
    display_name varchar(80) NOT NULL,
    role varchar(16) NOT NULL CHECK (role IN ('admin','viewer')),
    password_hash text NOT NULL CHECK (password_hash LIKE '$argon2id$%'),
    blocked boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE app_sessions (
    token_hash char(64) PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);
CREATE INDEX app_sessions_user_id ON app_sessions(user_id);
CREATE INDEX app_sessions_expires_at ON app_sessions(expires_at);
CREATE TABLE activity_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX activity_events_user_id_id ON activity_events(user_id,id DESC);
CREATE TABLE auth_limits (
    bucket varchar(64) PRIMARY KEY,
    started_at timestamptz NOT NULL,
    attempts integer NOT NULL CHECK (attempts > 0)
);
