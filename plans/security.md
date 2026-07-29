# Plan: Security Hardening

## Context

The NAS already has TLS via Caddy, Tailscale VPN, per-service user isolation, and firewall rules. This plan addresses the next layer: centralizing authentication, reducing container attack surface, and adding rate limiting at the reverse proxy.

---

## Security Review Findings (March 2026)

Full repository security review focused on Docker/Docker Compose best practices.
No high-confidence exploitable vulnerabilities found. The findings below are
defense-in-depth improvements.

### 1. Add `no-new-privileges` globally

> **Status: deferred follow-up (not done in the stacks restructure).** To be
> applied per-stack via a `x-hardened: &hardened` anchor merged into each
> service, rolled out one stack at a time so any breakage is attributable to
> the stack that changed.

No service uses `security_opt: [no-new-privileges:true]`. This flag prevents
setuid/setgid binaries inside a container from gaining elevated privileges. Add
it to every service via the per-stack `x-hardened` anchor.

### 2. Use `cap_drop: ALL` with selective `cap_add`

> **Status: deferred follow-up (not done in the stacks restructure).** Ships
> together with item 1 in the same per-stack `x-hardened` anchor, with minimal
> per-service `cap_add` exceptions determined empirically (start-and-observe):
> known so far are smartctl-exporter `SYS_RAWIO`, caddy `NET_BIND_SERVICE`, and
> the linuxserver s6 images (plex, qbittorrent) needing a
> `CHOWN/SETUID/SETGID/DAC_OVERRIDE`-class set.

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

`stacks/monitoring/alertmanager/entrypoint.sh` and
`stacks/monitoring/prometheus/entrypoint.sh` use `sed` for
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

`stacks/monitoring/alertmanager/entrypoint.sh` writes rendered config (containing SMTP password)
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
- New `stacks/infra/authelia/` directory with `configuration.yml`
- `stacks/infra/docker-compose.yml` — new Authelia service
- `stacks/infra/caddy/Caddyfile` — `forward_auth` directives for protected services

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
- each stack's `stacks/<stack>/docker-compose.yml` — security options per service (or the shared `x-hardened` anchor per stack)

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
- `stacks/infra/caddy/Dockerfile` — add `caddy-ratelimit` plugin
- `stacks/infra/caddy/Caddyfile` — rate limit directives for auth/login endpoints

---

## 8. User/Group Least-Privilege & Ownership-Drift Elimination

**Problem:** Two structural weaknesses in the user/group design:

1. `service_rw` is a single shared group with read/write on the whole `data`
   share. Every rw service (`qbittorrent`, `arr`, `ytdl`, `syncthing`,
   `immich`) can read/write *all* the others' data — a breakout in the most
   exposed container (`qbittorrent`, which fetches untrusted torrents) reaches
   the photo library and Personal data. The per-service UIDs give only the
   appearance of isolation; the shared group dissolves it.
2. Ownership is set once via `chown -R` with no inheritance mechanism. Every
   file an app or SMB write creates drifts from the baseline — the ownership
   audit command exists only to catch this.

### 8.1 Split `service_rw` into per-domain groups

- `media_rw` (rw) — members `arr`, `qbittorrent`, `ytdl`; owns `Media` +
  `Staging`. `plex` reads via its existing `:ro` bind mount, so it needs no
  write access and no membership.
- `immich` and `syncthing` each own their own tree
  (`Personal/Pictures/immich`, `Personal/Pictures/Synced`) under their **own
  private group** — the trees are disjoint, so no shared group is needed.
- Effect: a `qbittorrent` compromise is bounded to Media + Staging instead of
  all of `data`.
- Trade-off: Synology share permissions are share-level, so per-folder scoping
  (`media_rw` only on Media) must be expressed with folder/POSIX ACLs, not the
  DSM share-permission table.

**Files:**
- README `#### Groups` / `#### Users` tables — replace `service_rw` with
  `media_rw` and per-service groups
- `.env` — replace the shared `*_GID=65539` values with the new GIDs
- each stack's `docker-compose.yml` — updated `PGID` / `user:` values
- README ownership `chown -R` block — retarget to the new groups

### 8.2 Make ownership self-perpetuating (kill drift at the source)

- `chmod g+s` on every managed directory so new entries inherit the parent
  group instead of the creator's primary group.
- Default ACLs so new files get correct group perms regardless of the writer's
  umask:
  ```sh
  setfacl -R -m g:media_rw:rwX -m d:g:media_rw:rwX /volume1/data/Media /volume1/data/Staging
  setfacl -R -m g:backup:rX    -m d:g:backup:rX    /volume1/docker/appdata
  ```
- Demotes the ownership-audit scan from a routine chore to a rare safety net.
- Caveat: DSM overlays Synology ACLs on POSIX — verify `setfacl` defaults
  survive File Station and share-permission re-application before relying on
  them.

### 8.3 Pin a consistent umask

- The group scheme assumes files are group-readable; a container writing `0700`
  breaks `plex`/`restic` reads invisibly despite correct group ownership.
- Set `UMASK=002` for linuxserver images (`plex`, `qbittorrent`) and the
  equivalent for `immich`/`syncthing`; document the expectation.

**Files:** each stack's `docker-compose.yml` (`UMASK` env)

### 8.4 Reconcile the SMB `users` group

- SMB forces group `users` — this is the drift the scan keeps catching in
  `Personal/Pictures/immich` (photos dropped in over SMB that `immich` must
  read).
- Set a force-group / default group on that share in Synology's SMB advanced
  config so those writes land in `immich`'s group directly, instead of relying
  on periodic re-`chown`.

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
12. Ownership audit command (README) reports zero mismatches after retargeting groups + `setfacl`
13. `getfacl` on a managed dir shows the expected default (`d:`) ACL entries
14. Cross-domain isolation: as `qbittorrent`, confirm writes under `Personal/Pictures/immich` are denied
15. A new file written over SMB into `Personal/Pictures/immich` lands in `immich`'s group and is readable by `immich`
16. New files created by a service are group-readable (confirms `UMASK` applied)
