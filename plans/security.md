# Plan: Security Hardening

## Context

The NAS already has TLS via Caddy, Tailscale VPN, per-service user isolation, and firewall rules. This plan addresses the next layer: centralizing authentication, reducing container attack surface, and adding rate limiting at the reverse proxy.

---

## Security Review Findings (March 2026)

Full repository security review focused on Docker/Docker Compose best practices.
No high-confidence exploitable vulnerabilities found. The findings below are
defense-in-depth improvements.

### 1. Add `no-new-privileges` globally

No service uses `security_opt: [no-new-privileges:true]`. This flag prevents
setuid/setgid binaries inside a container from gaining elevated privileges. Add
it to every service in `docker-compose.yml`.

### 2. Use `cap_drop: ALL` with selective `cap_add`

`smartctl-exporter` adds `SYS_RAWIO` but doesn't drop other default
capabilities first. Change to:

```yaml
cap_drop:
  - ALL
cap_add:
  - SYS_RAWIO
```

Apply `cap_drop: [ALL]` to all other services that don't need any capabilities.

### 3. Pin upstream image versions

`plex` uses `lscr.io/linuxserver/plex:latest` — pin to a specific version tag
for reproducibility and to avoid silent supply-chain changes. Other upstream
images (prometheus, grafana, syncthing, etc.) are already pinned.

### 4. Switch entrypoint scripts from `sed` to `envsubst`

`alertmanager/entrypoint.sh` and `prometheus/entrypoint.sh` use `sed` for
variable substitution. The project's preferred approach (per CLAUDE.md) is
`envsubst` with explicit variable lists. Switch to:

```bash
envsubst '${SMTP_FROM},${SMTP_PASSWORD},${ALERT_EMAIL_TO}' \
    < /etc/alertmanager/alertmanager.yml.tpl > /tmp/alertmanager.yml
```

```bash
envsubst '${RESTIC_REST_SERVER_PORT}' \
    < /etc/prometheus/prometheus.yml.tpl > /etc/prometheus/prometheus.yml
```

This avoids metacharacter issues with `sed` delimiters and aligns with the
documented standard.

### 5. Restrict file permissions in entrypoint scripts

`alertmanager/entrypoint.sh` writes rendered config (containing SMTP password)
to `/tmp/alertmanager.yml` with default permissions (world-readable). While
single-process containers limit the risk, add `umask 077` before writing config
files that contain secrets.

---

## 5. Authelia or Caddy Forward Auth

**Problem:** Each service manages its own authentication independently. Prometheus has no auth at all. Anyone on the LAN or Tailscale network can access all services.

**Recommendation:**
- Deploy [Authelia](https://www.authelia.com/) as a lightweight SSO/2FA proxy
- Configure Caddy's `forward_auth` directive to gate access to sensitive services (Prometheus, Grafana, qBittorrent)
- Authelia supports TOTP 2FA, WebAuthn, and session management
- Services like Plex and Immich that have their own robust auth can bypass Authelia

**Files:**
- New `authelia/` directory with `configuration.yml`
- `docker-compose.yml` — new Authelia service
- `caddy/Caddyfile` — `forward_auth` directives for protected services

---

## 6. Container Security: Read-Only Rootfs & Drop Capabilities

**Problem:** Containers run with default Docker capabilities and writable root filesystems, which is more attack surface than needed.

**Recommendation:** For each service where feasible, add:
```yaml
security_opt:
  - no-new-privileges:true
read_only: true
tmpfs:
  - /tmp
cap_drop:
  - ALL
```
Add back only needed capabilities (e.g., `NET_BIND_SERVICE` for Caddy). The `smartctl-exporter` already uses `SYS_RAWIO` — that's fine, just don't add extras.

**Files:**
- `docker-compose.yml` — security options per service

---

## 7. Rate Limiting on Caddy

**Problem:** No rate limiting on the reverse proxy. If any service is exposed beyond Tailscale/LAN, it's vulnerable to brute force.

**Recommendation:** Add the `caddy-ratelimit` plugin to the custom Caddy build, and configure rate limits for auth endpoints:
```
rate_limit {
  zone login {
    key {remote_host}
    events 10
    window 1m
  }
}
```

**Files:**
- `caddy/Dockerfile` — add `caddy-ratelimit` plugin
- `caddy/Caddyfile` — rate limit directives for auth/login endpoints

---

## Verification

1. `docker compose config` — validate compose file syntax
2. `docker compose up --build -d` — deploy
3. `docker compose ps` — verify all containers healthy
4. Verify Authelia login page appears for protected services (Prometheus, Grafana, qBittorrent)
5. Confirm Plex and Immich are accessible without Authelia prompt
6. Verify TOTP 2FA works end-to-end
7. Confirm containers with `read_only: true` start correctly and write to tmpfs where needed
8. Test rate limiting: send >10 requests/min to a login endpoint and verify 429 responses
9. Verify `no-new-privileges` is applied: `docker inspect --format '{{.HostConfig.SecurityOpt}}' <container>`
10. Verify capabilities dropped: `docker inspect --format '{{.HostConfig.CapDrop}}' <container>`
11. Verify alertmanager/prometheus configs render correctly after switching from sed to envsubst
