# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NAS infrastructure-as-code repository for a Synology DS1821+ running Docker containers via docker-compose. All services are defined in a single `docker-compose.yml` with per-service subdirectories containing Dockerfiles, configs, and entrypoints.

## Commands

See the [Usage section in README.md](README.md#usage) for all docker-compose
commands. There are no tests or linters — this is a declarative infrastructure
repo.

## Architecture

### Networking (dual-network design)

Caddy is the only container on both networks, bridging external access to internal services:

- **macvlan** (192.168.2.0/24, parent: eth0): Caddy at 192.168.2.3 — bypasses Synology's built-in Nginx to get clean ports 80/443 with wildcard subdomain support
- **bridge** (172.18.0.0/16): All containers communicate here; Caddy at 172.18.0.3 reverse-proxies to services by container name/IP
- **host network**: Syncthing (local discovery requires it) and gallery-dl

Tailscale advertises the bridge subnet (172.18.0.0/16) for remote access. DNS records (*.nas.ts.hashhar.com) point to Caddy's bridge IP.

See the [Docker macvlan Networking appendix](README.md#docker-macvlan-networking) and [Tailscale Routing](README.md#tailscale-routing) in README for setup commands and rationale.

### Configuration patterns

- **`.env`**: Shared variables for docker-compose interpolation (paths, UIDs/GIDs, ports). Not injected into containers.
- **`<service>/secrets.env`**: Per-service secrets injected via `env_file:`. Git-ignored. Any service that requires secrets needs one of these. When adding one, document the required variables and their purpose in `README.md` under a `### <ServiceName>` entry in the Special Instructions section. See [Environment Files in README](README.md#environment-files) for full operational guidance.
- **`<service>/secrets.env.example`**: Tracked template showing required variable names and how to obtain values. Copy to `secrets.env` and fill in real values.
- **Build-time templating** (being phased out): Dockerfiles use multi-stage builds — Alpine+gettext `envsubst` or `sed` to bake config templates with build args, then copy into final image.
- **Runtime templating** (preferred): Config templates (`.tpl` files) are mounted into containers and rendered at startup via `envsubst`. See "Configuration refactoring" below.

### Configuration refactoring

#### Goals

1. **Use upstream images where possible** — eliminate custom Dockerfiles that exist only to bake config into the image
2. **Version-controlled configuration** — all config templates live in the repo
3. **No secrets in the repo** — credentials go in gitignored `<service>/secrets.env` files, injected via environment variables
4. **Single source of truth** — changing a value must not require edits in multiple places; `.env` and `secrets.env` are the only places values are defined
5. **Decouple runtime-modified config from repo** — apps that modify their own config at runtime (e.g. qBittorrent) must not write back to repo-tracked files; templates are rendered to a separate location on each start

#### Approach: Runtime envsubst

Render config templates at container startup using `envsubst`. Variables come from the container environment (set via `environment:` and `env_file:` in docker-compose.yml, sourced from `.env` and `secrets.env`).

- **linuxserver-based images** (qBittorrent): Use `/custom-cont-init.d/` scripts that run during the s6 init sequence
- **Other images** (Prometheus, Alertmanager): Use an entrypoint wrapper script that runs `envsubst`, writes the rendered config, then `exec`s the original entrypoint
- **Template naming**: Use `.tpl` extension to signal "this file has placeholders"

#### Alternatives considered and rejected

| Approach | Why rejected |
|----------|-------------|
| **Build-time envsubst** (current) | Bakes rendered config including secrets into image layers; requires rebuild for any config change |
| **Makefile pre-rendering** | Adds a manual `make render` step; forgetting it deploys stale config — directly contradicts the single-source-of-truth goal |
| **Multi-stage build copying only the envsubst binary** | Still a custom image; acceptable as a fallback if runtime package install isn't possible, but not preferred |

#### Risks

1. **Network dependency** — `apk add gettext` at runtime requires Alpine repos to be reachable. For a NAS that should survive network outages, consider falling back to the multi-stage approach (copy `envsubst` binary into a thin custom image layer) for critical services if this becomes an issue.
2. **envsubst variable scope** — Without an explicit variable list, `envsubst` replaces ALL `$VAR` patterns in the file. Always use explicit variable lists: `envsubst '${VAR1},${VAR2}' < template > output`.
3. **Credential handling with overwrite-on-restart** — For apps that allow credential changes via UI (e.g. qBittorrent), the startup script overwrites config on every restart. Credentials must be envsubst variables sourced from `secrets.env`, not hardcoded in templates, or they'll be wiped on restart.

#### When a custom Dockerfile is necessary

A custom Dockerfile is justified when:
- The upstream image needs a plugin or binary that requires a custom build (e.g. Caddy with xcaddy + Cloudflare DNS plugin)
- No upstream image exists at all (e.g. gallery-dl)

A custom Dockerfile is **not** justified when its only purpose is to bake config or install a single package (`gettext`, `su-exec`, etc.) that could be handled at runtime.

When in doubt, prefer the runtime envsubst approach and drop the Dockerfile. If the base image truly cannot run `apk add` at startup (no network, read-only fs), the fallback is a multi-stage Dockerfile that copies only the `envsubst` binary — no config or secrets are baked in.

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

See [Directory Setup in README](README.md#directory-setup) for the full tree.

### User/group isolation

Each service runs as a dedicated Synology user with a specific UID/GID (defined in `.env`). Groups control share-level access: `service_ro` for read-only (plex), `service_rw` for read-write (qbittorrent, syncthing, immich), `backup` for restic.

See [User & Group in README](README.md#user--group) for the full permission tables.

### Dependabot

`.github/dependabot.yml` tracks image version updates weekly via two ecosystems:

- **`docker` ecosystem**: one entry per service directory that contains a custom Dockerfile; watches for base image bumps
- **`docker-compose` ecosystem**: one entry per directory containing a `docker-compose.yml`; ignores `hashhar/*` images (built locally, not from a registry) and any images pinned to a specific custom build

**Rules:**
- Adding a custom Dockerfile → add the service directory to the `docker` ecosystem
- Removing a custom Dockerfile → remove the service directory from the `docker` ecosystem
- Adding a new docker-compose file in a new subdirectory → add that directory to the `docker-compose` ecosystem
- Pinning an image to a custom/non-standard tag → add it to the `ignore` list with a comment explaining why

### Keeping documentation in sync

`README.md` is the setup manual for this repo — it contains the step-by-step instructions a human needs to get everything running from scratch. Keep it accurate.

| Change | What to update |
|--------|---------------|
| Add a service with a `secrets.env` | Add a `### <ServiceName>` entry under "Special Instructions" in README documenting each required variable, its purpose, and how to generate/obtain it; and add a `secrets.env.example` with all required variables |
| Remove a service with a `secrets.env` | Remove its Special Instructions entry from README |
| Add a new Synology user for a service | Add the user to the Users table in README |
| Add a custom Dockerfile | Add the service directory to the `docker` ecosystem in `dependabot.yml` |
| Remove a custom Dockerfile | Remove the service directory from the `docker` ecosystem in `dependabot.yml` |
| Add a new docker-compose file | Add the directory to the `docker-compose` ecosystem in `dependabot.yml` |
| Pin an upstream image to a non-standard tag | Add to `ignore` list in `dependabot.yml` with a comment explaining why |
| Change a port, path, or significant config default | Check whether README references it and update accordingly |

### Monitoring

Prometheus scrapes: itself, caddy (:80/metrics), restic-rest-server, immich (API :8081, microservices :8082), smartctl-exporter, node-exporter. Alert rules in `prometheus/alerts.yml` cover SMART disk health, RAID degradation, filesystem space, and service availability. Alertmanager routes alerts to email via Gmail SMTP.
