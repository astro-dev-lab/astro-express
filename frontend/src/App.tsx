import { useEffect, useState } from "react";
import { api, ApiError, type Session, type Provider, type Result } from "./api";
const details: Record<string, { icon: string; copy: string }> = {
  stripe: {
    icon: "S",
    copy: "Explore a synthetic checkout and a declined payment.",
  },
  hubspot: {
    icon: "H",
    copy: "Qualify a fictional contact or test a duplicate record.",
  },
  notion: {
    icon: "N",
    copy: "Create a fixture page or simulate a permission error.",
  },
  resend: { icon: "R", copy: "Queue a simulated email or inspect a bounce." },
  twilio: {
    icon: "T",
    copy: "Try an SMS fixture or an invalid number scenario.",
  },
  google: {
    icon: "G",
    copy: "Simulate a calendar event or an authorization rejection.",
  },
};
export default function App() {
  const [session, setSession] = useState<Session | null>(null),
    [authConfig, setAuthConfig] = useState<{mode: "simulation" | "production"; credential_login: boolean} | null>(null),
    [username, setUsername] = useState(""),
    [password, setPassword] = useState(""),
    [checking, setChecking] = useState(true),
    [providers, setProviders] = useState<Provider[]>([]),
    [events, setEvents] = useState<Result[]>([]),
    [busy, setBusy] = useState<string | null>(null),
    [error, setError] = useState(""),
    [result, setResult] = useState<Result | null>(null);
  function fail(e: unknown) {
    setError(
      e instanceof ApiError
        ? e.message
        : "Unable to reach the local demo server. Check that it is running and try again.",
    );
    if (e instanceof ApiError && e.status === 401) {
      setSession(null);
      setProviders([]);
      setEvents([]);
      setResult(null);
    }
  }
  async function refresh() {
    const [cards, history] = await Promise.all([
      api<{ integrations: Provider[] }>("/api/integrations"),
      api<{ events: Result[] }>("/api/activity"),
    ]);
    setProviders(cards.integrations);
    setEvents(history.events);
  }
  useEffect(() => {
    let active = true;
    api<{mode: "simulation" | "production"; credential_login: boolean}>("/api/auth/config")
      .then(config => {
        if (active) setAuthConfig(config);
        return api<Session>("/api/auth/me");
      })
      .then(async (s) => {
        if (active) {
          setSession(s);
          await refresh();
        }
      })
      .catch((e) => {
        if (active && !(e instanceof ApiError && e.status === 401)) fail(e);
      })
      .finally(() => {
        if (active) setChecking(false);
      });
    return () => {
      active = false;
    };
  }, []);
  async function login() {
    setBusy("login");
    setError("");
    try {
      if (!authConfig) return;
      const credentialLogin = authConfig.mode === "production" && authConfig.credential_login;
      const s = await api<Session>(credentialLogin ? "/api/auth/login" : "/api/auth/demo-login", undefined, credentialLogin ? {username, password} : {});
      setSession(s);
      await refresh();
    } catch (e) {
      if (authConfig?.mode === "production" && e instanceof ApiError && [401, 403, 422].includes(e.status))
        setError("Unable to sign in. Check your credentials and try again.");
      else fail(e);
    } finally {
      setPassword("");
      setBusy(null);
    }
  }
  async function logout() {
    setBusy("logout");
    setError("");
    try {
      await api("/api/auth/logout", session?.csrf_token, {});
      setSession(null);
      setProviders([]);
      setEvents([]);
      setResult(null);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  }
  async function run(provider: string, action: string) {
    if (session?.user.role === "viewer") return;
    setBusy(provider);
    setError("");
    try {
      setResult(
        await api<Result>(
          `/api/integrations/${provider}/simulate`,
          session?.csrf_token,
          { action },
        ),
      );
      await refresh();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  }
  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="ME Astro Fast home">
          <span className="brand-mark">✳</span>
          <span>
            me astro <strong>fast</strong>
          </span>
        </a>
        <span className="local-label">
          <span /> {authConfig?.mode === "production" ? "PROTECTED WORKSPACE" : "LOCAL DEMO"}
        </span>
        {session && (
          <button className="signout" onClick={logout} disabled={busy !== null}>
            Sign out
          </button>
        )}
      </header>
      {busy && (
        <p className="sr-only" role="status" aria-live="polite">
          {busy === "login"
            ? "Opening demo workspace"
            : busy === "logout"
              ? "Signing out"
              : "Running local simulation"}
        </p>
      )}
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      {checking ? (
        <main className="login">
          <p role="status">Opening your local workspace…</p>
        </main>
      ) : !session ? (
        <main className="login">
          <div className="eyebrow">YOUR OFFLINE WORKFLOW PLAYGROUND</div>
          <h1>
            Big workflows.
            <br />
            <span>Zero live connections.</span>
          </h1>
          <p className="intro">
            Explore six everyday integrations in one focused workspace. Every
            action uses synthetic fixtures and stays inside this local demo.
          </p>
          {authConfig?.mode === "production" && authConfig.credential_login ? (
            <form className="credential-form" onSubmit={event => {event.preventDefault(); void login();}}>
              <label htmlFor="username">Username</label>
              <input id="username" name="username" autoComplete="username" required value={username} onChange={event => setUsername(event.target.value)} disabled={busy !== null}/>
              <label htmlFor="password">Password</label>
              <input id="password" name="password" type="password" autoComplete="off" required value={password} onChange={event => setPassword(event.target.value)} disabled={busy !== null}/>
              <button className="primary" type="submit" disabled={busy !== null}>{busy === "login" ? "Signing in…" : "Sign in"}</button>
              <p className="login-note">Use your provisioned workspace credentials. Provider workflows remain simulated.</p>
            </form>
          ) : authConfig?.mode === "simulation" ? (<>
            <button className="primary" onClick={login} disabled={busy !== null}>
              {busy === "login" ? "Opening workspace…" : "Enter demo workspace"} <span aria-hidden="true">↗</span>
            </button>
            <p className="login-note">Sign in as Demo Operator. No account, password, or personal data needed.</p>
          </>) : <p role="status">Sign-in configuration unavailable.</p>}
          <div className="login-chips">
            {Object.keys(details).map((id) => (
              <span key={id}>
                {id === "hubspot"
                  ? "HubSpot"
                  : id.charAt(0).toUpperCase() + id.slice(1)}
              </span>
            ))}
          </div>
        </main>
      ) : (
        <main className="dashboard">
          <section className="heading">
            <div>
              <div className="eyebrow">WORKSPACE / OVERVIEW</div>
              <h1>
                Your integration lab<span>.</span>
              </h1>
              <p>
                Welcome, {session.user.display_name}. Put a workflow through its
                paces.
              </p>
            </div>
            <div className="session-state">
              <span className="status-dot" /> {authConfig?.mode === "production" ? "Session active" : "Demo session active"}
            </div>
          </section>
          <div className="simulation-banner">
            <span aria-hidden="true">◈</span>
            <div>
              <strong>SIMULATION — NO LIVE CONNECTIONS</strong>
              <p>
                Fixtures only. No payments, messages, account connections, or
                external writes.
              </p>
            </div>
            <span className="offline-pill">100% local</span>
          </div>
          <section className="section-title">
            <h2>Connected ideas. Simulated actions.</h2>
            <span>6 integration playgrounds</span>
          </section>
          {session.user.role === "viewer" && <p id="viewer-hint" className="login-note">Read-only access. An administrator can run simulation scenarios.</p>}
          <div className="cards">
            {providers.map((p) => (
              <article className={`card ${p.id}`} key={p.id}>
                <div className="card-top">
                  <div className="provider-icon" aria-hidden="true">
                    {details[p.id]?.icon ?? p.name[0]}
                  </div>
                  <span className="mode">SIMULATED</span>
                </div>
                <h3>{p.name}</h3>
                <p>
                  {details[p.id]?.copy ??
                    "Explore deterministic synthetic workflow scenarios."}
                </p>
                <div className="connection">
                  <span /> NOT CONNECTED
                </div>
                {authConfig?.mode === "production" && <p className="login-note">SANDBOX NOT CONFIGURED</p>}
                <div className="actions">
                  {p.actions.map((a, index) => {
                    const id = typeof a === "string" ? a : a.id,
                      label =
                        typeof a === "string"
                          ? a.replaceAll("-", " ")
                          : a.label;
                    return (
                      <button
                        key={id}
                        className={
                          index === 0 ? "action-success" : "action-failure"
                        }
                        aria-label={`${p.name}: ${label}`}
                        aria-describedby={session.user.role === "viewer" ? "viewer-hint" : undefined}
                        disabled={busy !== null || session.user.role === "viewer"}
                        onClick={() => run(p.id, id)}
                      >
                        {busy === p.id ? "Running…" : label}
                        <span aria-hidden="true">
                          {index === 0 ? "↗" : "⌁"}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </article>
            ))}
          </div>
          {result && (
            <section
              className={`result ${result.status}`}
              role="status"
              aria-live="polite"
            >
              <div>
                <span className="eyebrow">
                  LATEST SIMULATION / {result.provider}
                </span>
                <h2>
                  {result.status === "success"
                    ? "Scenario completed"
                    : "Failure scenario reproduced"}
                </h2>
                <p>
                  {result.message ?? "Synthetic fixture returned successfully."}
                </p>
              </div>
              <div className="reference">
                <span>DEMO REFERENCE</span>
                <code>{result.reference}</code>
              </div>
            </section>
          )}
          <section className="activity">
            <div className="section-title">
              <h2>Session activity</h2>
              <span>
                {events.length} {events.length === 1 ? "event" : "events"} ·
                this session only
              </span>
            </div>
            {events.length === 0 ? (
              <div className="empty">
                <span aria-hidden="true">↗</span>
                <h3>Your first experiment starts here.</h3>
                <p>
                  Run any scenario above to see its outcome and demo reference.
                </p>
              </div>
            ) : (
              <ol>
                {events.map((e) => (
                  <li key={e.reference}>
                    <span className={`event-dot ${e.status}`} />
                    <div>
                      <strong>
                        {e.provider}{" "}
                        <span> / {e.action?.replaceAll("-", " ")}</span>
                      </strong>
                      <p>{e.message}</p>
                      <code>{e.reference}</code>
                    </div>
                    <span className={`event-status ${e.status}`}>
                      {e.status === "success" ? "Success" : "Expected failure"}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </main>
      )}
      <footer>
        <span>ME Astro Fast · {authConfig?.mode === "production" ? "P1 foundation / regression fixtures" : "Local regression lab"}</span>
        <span>Synthetic data. Real interaction.</span>
      </footer>
    </div>
  );
}
