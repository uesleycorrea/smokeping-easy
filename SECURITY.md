# Security Policy

## Reporting a vulnerability

Please report security issues **privately** by opening a
[GitHub Security Advisory](../../security/advisories/new) or by email to the
maintainer. Do not open a public issue for undisclosed vulnerabilities. We aim
to acknowledge reports within a few days.

## Security model

smokeping-easy is designed to be exposed only to trusted operators. Its
defenses:

### Authentication & sessions
- Single admin password, hashed with **bcrypt** (cost 12). The plaintext
  `ADMIN_PASSWORD` is used only to seed the hash on first boot and is never
  written to disk.
- **Server-side sessions**; the cookie holds only an opaque random token and is
  `HttpOnly` + `SameSite=Strict` (and `Secure` when running behind TLS).
- Changing the password invalidates all existing sessions.
- Sessions expire after `SESSION_TTL_MINUTES` (default 120).

### Rate limiting
- Login is limited to **5 failed attempts per IP per 10 minutes** (configurable);
  the 6th is rejected with `429` and a `Retry-After`.
- nginx applies additional per-IP request rate limits on `/api` and the login
  endpoint.

### Input validation
- Every `host` is validated (`validators.validate_host`) as an IPv4/IPv6 literal
  or a strict RFC-1123 hostname before it is written to config or used in a
  path — this rejects all shell metacharacters and whitespace.
- Every RRD path is built with `validators.safe_rrd_path`, which refuses path
  traversal (`..`, separators) and confirms the resolved path stays inside the
  data directory.
- The backend is the source of truth for validation; the frontend only
  validates for UX.

### Secrets at rest
- Telegram bot token / chat id and the AI API key are encrypted with
  **Fernet** (AES-128-CBC + HMAC) in `settings.json`, prefixed `encrypted:`.
- The Fernet key `secret.key` is generated on first boot with `chmod 600` and
  is git-ignored — **never commit it**.
- The API never returns decrypted secrets; it only reports whether each is set.

### Network exposure
- Only the frontend (nginx) publishes a port. The **backend never exposes a
  port** to the host — it is reachable only through the nginx `/api` proxy.
- The Smokeping **reload API listens on internal port 9000** and is never
  mapped to the host; it is protected by a shared `RELOAD_TOKEN`.
- No Docker socket is mounted into the app containers. (The optional Traefik
  TLS overlay mounts the socket **read-only** into Traefik only — a standard
  Traefik requirement; review before using in hostile environments.)

### Containers
- Backend runs as a **non-root** user (UID/GID = `PUID`/`PGID`).
- Frontend uses the **unprivileged nginx** image (uid 101, listens on 8080).
- Smokeping runs its services as the unprivileged `abc` user (the s6 init
  supervisor runs as root by design in LinuxServer images).

### HTTP security headers (nginx)
- A restrictive `Content-Security-Policy` (`default-src 'self'`; scripts only
  from self and the pinned jsDelivr CDN), plus `X-Frame-Options`,
  `X-Content-Type-Options: nosniff`, `Referrer-Policy`, and `Permissions-Policy`.

### Logging
- The access-log middleware never logs request/response bodies and **redacts**
  sensitive fields (`api_key`, `password`, `bot_token`, `chat_id`, `token`,
  `secret`, …) including in query strings.
- Default `LOG_LEVEL` is `INFO`; avoid `DEBUG` in production.

### Dependencies
- All Python dependencies are **pinned to exact versions**; CDN assets are
  pinned by version **and** Subresource Integrity (SRI) hashes.
- Dependabot proposes updates weekly.

## Hardening checklist for operators
1. Set a long, random `ADMIN_PASSWORD` and `RELOAD_TOKEN` in `.env` before the
   first boot, then change the admin password again from the UI.
2. Run behind TLS (`docker-compose.tls.yml`) so the session cookie is `Secure`.
3. Restrict who can reach the published HTTP port (firewall / reverse proxy).
4. Keep the stack updated (merge Dependabot PRs).
