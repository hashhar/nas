# Plan: Security Hardening

## Context

The NAS already has TLS via Caddy, Tailscale VPN, per-service user isolation, and firewall rules. This plan addresses the next layer: centralizing authentication, reducing container attack surface, and adding rate limiting at the reverse proxy.

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
