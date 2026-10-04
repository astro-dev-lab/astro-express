# Security boundary

P0 is a synthetic local demonstration. Anyone using the local browser can select the fictional operator. Do not expose it to public networks or use it for real identities/data. Run one worker on `127.0.0.1`; sessions and logs are temporary.

Security review verifies opaque random cookies, HttpOnly/SameSite controls, logout/expiry, Origin and CSRF validation, loopback Host/config enforcement, strict inputs, bounded memory, local static assets, and vendor no-egress. No default JWT secret is used. Live and production modes are unsupported.

Runtime does not enforce an operating-system network sandbox. No-egress evidence combines source review with socket-denied endpoint tests and browser request checks. Defense in depth can use a network-isolated environment allowing only local browser traffic.

Install tools contact package registries; Git fetch/handoff contacts GitHub. Those operations do not exercise vendor integrations. No workflow, cloud deployment, external account provisioning, or paid service is part of P0.

Dependency advisory scanning is separate from functional tests. Passing tests do not prove all dependencies vulnerability-free. See verification and independent QA reports for actual checks and remaining limits.
