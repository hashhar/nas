# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NAS infrastructure-as-code repository for a Synology DS1821+ running Docker containers via docker-compose. All services are defined in a single `docker-compose.yml` with per-service subdirectories containing Dockerfiles, configs, and entrypoints.

## Commands

```sh
# Build and start all services
docker-compose up --build --detach

# Stop services
docker-compose stop

# Pull updated images
docker-compose pull

# Start without rebuilding
docker-compose up --detach --no-recreate

# Run gallery-dl (profile-gated, exits when done)
docker-compose --profile gallery-dl up --build --detach gallery-dl

# Remote ML workers for Immich (run on separate machines)
MACHINE_LEARNING_WORKERS=2 docker compose -f immich/docker-compose.remote-ml.yml up -d        # CPU
MACHINE_LEARNING_WORKERS=3 docker compose -f immich/docker-compose.remote-ml-cuda.yml up -d    # CUDA
```

There are no tests or linters — this is a declarative infrastructure repo.

## Architecture

### Networking (dual-network design)

Caddy is the only container on both networks, bridging external access to internal services:

- **macvlan** (192.168.2.0/24, parent: eth0): Caddy at 192.168.2.3 — bypasses Synology's built-in Nginx to get clean ports 80/443 with wildcard subdomain support
- **bridge** (172.18.0.0/16): All containers communicate here; Caddy at 172.18.0.3 reverse-proxies to services by container name/IP
- **host network**: Syncthing (local discovery requires it) and gallery-dl

Tailscale advertises the bridge subnet (172.18.0.0/16) for remote access. DNS records (*.nas.ts.hashhar.com) point to Caddy's bridge IP.

### Configuration patterns

- **`.env`**: Shared variables for docker-compose interpolation (paths, UIDs/GIDs, ports). Not injected into containers.
- **`<service>/secrets.env`**: Per-service secrets injected via `env_file:`. Git-ignored. Required for: caddy (CF_API_TOKEN), alertmanager (SMTP creds), grafana (admin password), immich (DB password).
- **Build-time templating**: Dockerfiles use multi-stage builds — Alpine+gettext `envsubst` (prometheus, qbittorrent) or `sed` (alertmanager) to bake config templates with build args, then copy into final image.
- **Runtime templating**: alertmanager's `entrypoint.sh` does `sed` substitution of secrets at container start.

### Service categories

| Category | Services |
|----------|----------|
| Media | plex (read-only media), qbittorrent (downloads to Staging), gallery-dl (profile-gated) |
| Photos | immich-server, immich-machine-learning, immich-redis, immich-database |
| Sync | syncthing (host network) |
| Monitoring | prometheus, grafana, alertmanager, smartctl-exporter (8 SATA devices), node-exporter |
| Infrastructure | caddy (reverse proxy + TLS via Cloudflare DNS challenge), restic-rest-server (backups) |

### Storage layout

All containers mount under two roots to avoid cross-filesystem copies:
- `DOCKER_DATA=/volume1/docker/appdata` — container configs and state
- `DATA_ROOT=/volume1/data` — user data (Media, Personal, Staging, etc.)

Plex mounts Media as read-only. qBittorrent writes to Staging. The *arr apps (not yet containerized) move files from Staging to Media.

### User/group isolation

Each service runs as a dedicated Synology user with a specific UID/GID (defined in `.env`). Groups control share-level access: `service_ro` for read-only (plex), `service_rw` for read-write (qbittorrent, syncthing, immich), `backup` for restic.

### Custom Dockerfiles

- **caddy**: xcaddy build with cloudflare DNS plugin
- **qbittorrent**: Alpine builder runs envsubst on config templates, copies into linuxserver/qbittorrent base
- **prometheus**: Alpine builder runs envsubst on prometheus.yml, copies into prom/prometheus base
- **alertmanager**: Custom entrypoint.sh runs sed on alertmanager.yml at startup for secret substitution
- **restic-rest-server**: Adds su-exec for PUID/PGID support
- **gallery-dl**: Python 3.14-alpine with yt-dlp and ffmpeg

### Monitoring

Prometheus scrapes: itself, caddy (:80/metrics), restic-rest-server, immich (API :8081, microservices :8082), smartctl-exporter, node-exporter. Alert rules in `prometheus/alerts.yml` cover SMART disk health, RAID degradation, filesystem space, and service availability. Alertmanager routes alerts to email via Gmail SMTP.
