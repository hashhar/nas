# TODO: Friend Access Architecture

## Context

Expose NAS services to friends securely. Behind CGNAT, so no port forwarding. Cloudflare Tunnel violates TOS for video/image serving (Section 2.8). Tailscale node sharing chosen as the single remote access method for both admin and friends.

## Tasks

### 1. Tailscale ACLs (do first, before inviting friends)

- [ ] Configure ACLs in Tailscale admin console (`https://login.tailscale.com/admin/acls`)
- [ ] `group:admin` (your devices) -> full access to `172.18.0.0/16:*`
- [ ] `group:friends` (shared nodes) -> access to `172.18.0.3:443` only (Caddy HTTPS)
- [ ] Test: from a device in `group:friends`, confirm access to Caddy but not to backend IPs directly

### 2. Deploy Authelia

- [ ] Create `stacks/infra/authelia/configuration.yml` (session domain `hashhar.com`, file-based user DB, TOTP 2FA, SQLite storage, SMTP via Gmail)
- [ ] Create `stacks/infra/authelia/users_database.yml` (admin user with bcrypt-hashed password)
- [ ] Add the Authelia service to the **infra** stack (`stacks/infra/docker-compose.yml`, image `authelia/authelia:4`). No static IP pin needed — it's reached by container name (`authelia`) over `nas_bridge`, and the bridge's `--ip-range` carve-out keeps dynamic IPs off the pinned range. (Supersedes the old `172.18.0.17` allocation.)

### 3. Modify Caddyfile for forward_auth

- [ ] Add `proxy-host-protected` snippet with `forward_auth authelia:9091` to `stacks/infra/caddy/Caddyfile`
- [ ] Add `authelia` to the `map` block for known subdomains
- [ ] Add unprotected `proxy-host` route for `authelia` itself (the login portal)
- [ ] Change admin services to use `proxy-host-protected`: qbittorrent, syncthing, restic-rest-server, prometheus, grafana
- [ ] Keep friend-accessible services on `proxy-host` (no Authelia): plex, immich

### 4. Invite friends

- [ ] Share NAS Tailscale node with friend (via `tailscale share` or admin console)
- [ ] Create Plex accounts (via plex.tv sharing)
- [ ] Create Immich accounts (via admin UI)
- [ ] Share URLs: `https://plex.nas.ts.hashhar.com`, `https://immich.nas.ts.hashhar.com`

## Authentication Tiers

| Tier | Services | Auth Method |
|------|----------|-------------|
| Friend-accessible | Plex, Immich | Built-in app auth (don't put Authelia in front -- breaks client apps) |
| Admin-only | Prometheus, Grafana, Alertmanager, qBittorrent, Syncthing, Restic | Authelia forward_auth via Caddy |
| Internal-only | Databases, Redis, ML worker, exporters | Already unreachable from outside Docker |

## Metrics Security

All `/metrics` endpoints are either bridge-internal (scraped by Prometheus directly) or covered by Authelia on admin subdomains. No additional rules needed.

## Verification

- [ ] Admin over Tailscale: all services accessible, Authelia prompts for admin services only
- [ ] Friend over Tailscale: Plex/Immich work, admin services show Authelia login, direct IP access blocked
- [ ] LAN: all services work as before, Authelia protects admin services
- [ ] Plex streaming: verify "Direct Play" (not relay) from friend's device
- [ ] Immich upload: verify photo upload from friend's phone
